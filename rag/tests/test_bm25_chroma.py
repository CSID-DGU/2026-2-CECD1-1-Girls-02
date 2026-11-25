from __future__ import annotations

import threading
import unittest

from rag.app.ingestion import Chunk
from rag.app.retrieval.bm25 import basic_tokenize, kiwi_tokenize
from rag.app.retrieval.bm25_chroma import (
    BM25ChromaConnectionError,
    BM25ChunkLoadError,
    BM25CollectionChangedError,
    BM25IndexManager,
    BM25IndexUnavailableError,
    BM25NoApprovedChunksError,
    BM25OfficialCollectionEmptyError,
    BM25OfficialCollectionNotFoundError,
    BM25RebuildInProgressError,
    OfficialChromaChunkLoader,
    OfficialChunkSnapshot,
)
from rag.app.retrieval.contracts import KnowledgeScope, SearchFilter, SearchRequest


def _metadata(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "document_id": "faq:1",
        "source_id": "faq:1",
        "document_version": "v1",
        "category": "COUPON",
        "knowledge_scope": "official",
        "is_active": True,
        "review_status": "APPROVED",
        "allowed_use": "DRAFT_ONLY",
    }
    value.update(overrides)
    return value


class FakeCollection:
    def __init__(self, rows, *, counts=None, error=None):
        self.rows = list(rows)
        self.counts = list(counts) if counts is not None else None
        self.error = error
        self.get_calls = []

    def count(self):
        if self.counts is not None:
            return self.counts.pop(0)
        return len(self.rows)

    def get(self, **kwargs):
        if self.error:
            raise self.error
        self.get_calls.append(kwargs)
        start = kwargs["offset"]
        page = self.rows[start : start + kwargs["limit"]]
        return {
            "ids": [row[0] for row in page],
            "documents": [row[1] for row in page],
            "metadatas": [row[2] for row in page],
        }


class FakeClient:
    def __init__(self, collection=None, *, heartbeat_error=None, collection_error=None):
        self.collection = collection
        self.heartbeat_error = heartbeat_error
        self.collection_error = collection_error

    def heartbeat(self):
        if self.heartbeat_error:
            raise self.heartbeat_error
        return 1

    def get_collection(self, *, name):
        if self.collection_error:
            raise self.collection_error
        return self.collection


class OfficialChromaChunkLoaderTests(unittest.TestCase):
    def test_loads_all_pages_and_preserves_chunk_contract(self) -> None:
        rows = [
            ("chunk-1", "쿠폰 안내", _metadata()),
            ("chunk-2", "배송 안내", _metadata(document_id="faq:2", source_id="faq:2")),
            ("chunk-3", "포장 안내", _metadata(document_id="faq:3", source_id="faq:3")),
        ]
        collection = FakeCollection(rows)
        snapshot = OfficialChromaChunkLoader(
            collection, collection_name="brand_a_official_knowledge", page_size=2
        ).load()

        self.assertEqual(snapshot.chunk_ids, ("chunk-1", "chunk-2", "chunk-3"))
        self.assertEqual(snapshot.chunks[1].text, "배송 안내")
        self.assertEqual(snapshot.chunks[1].metadata["document_id"], "faq:2")
        self.assertEqual(snapshot.chunks[1].metadata["document_version"], "v1")
        self.assertEqual([call["offset"] for call in collection.get_calls], [0, 2])
        self.assertTrue(all(call["where"]["$and"] for call in collection.get_calls))

    def test_post_filters_unsafe_rows(self) -> None:
        rows = [
            ("approved", "쿠폰", _metadata()),
            ("pending", "쿠폰", _metadata(review_status="PENDING_REVIEW")),
            ("inactive", "쿠폰", _metadata(is_active=False)),
        ]
        snapshot = OfficialChromaChunkLoader(
            FakeCollection(rows), collection_name="official"
        ).load()
        self.assertEqual(snapshot.chunk_ids, ("approved",))

    def test_distinguishes_empty_and_no_approved_collection(self) -> None:
        with self.assertRaises(BM25OfficialCollectionEmptyError):
            OfficialChromaChunkLoader(FakeCollection([]), collection_name="official").load()
        with self.assertRaises(BM25NoApprovedChunksError):
            OfficialChromaChunkLoader(
                FakeCollection([("pending", "text", _metadata(review_status="PENDING_REVIEW"))]),
                collection_name="official",
            ).load()

    def test_rejects_duplicates_and_missing_required_metadata(self) -> None:
        duplicate = [("same", "one", _metadata()), ("same", "two", _metadata())]
        with self.assertRaisesRegex(BM25ChunkLoadError, "Duplicate"):
            OfficialChromaChunkLoader(FakeCollection(duplicate), collection_name="official").load()
        missing = _metadata()
        del missing["document_version"]
        with self.assertRaisesRegex(BM25ChunkLoadError, "document_version"):
            OfficialChromaChunkLoader(
                FakeCollection([("chunk", "text", missing)]), collection_name="official"
            ).load()

    def test_distinguishes_connection_missing_collection_and_query_errors(self) -> None:
        with self.assertRaises(BM25ChromaConnectionError):
            OfficialChromaChunkLoader.connect(
                client_factory=lambda **_: FakeClient(heartbeat_error=OSError("offline"))
            )

        class NotFoundError(Exception):
            pass

        with self.assertRaises(BM25OfficialCollectionNotFoundError):
            OfficialChromaChunkLoader.connect(
                client_factory=lambda **_: FakeClient(
                    collection_error=NotFoundError("collection not found")
                )
            )
        with self.assertRaisesRegex(BM25ChunkLoadError, "offset 0"):
            OfficialChromaChunkLoader(
                FakeCollection([("chunk", "text", _metadata())], error=OSError("query failed")),
                collection_name="official",
            ).load()

    def test_aborts_when_collection_count_changes_during_pagination(self) -> None:
        collection = FakeCollection(
            [("chunk", "text", _metadata())], counts=[1, 2]
        )
        with self.assertRaises(BM25CollectionChangedError):
            OfficialChromaChunkLoader(collection, collection_name="official").load()

    def test_same_ids_versions_and_text_produce_same_snapshot_id(self) -> None:
        rows = [("chunk", "same text", _metadata(document_version="v2"))]
        first = OfficialChromaChunkLoader(FakeCollection(rows), collection_name="official").load()
        second = OfficialChromaChunkLoader(FakeCollection(rows), collection_name="official").load()
        self.assertEqual(first.snapshot_id, second.snapshot_id)


def _snapshot(chunk_id: str, text: str, snapshot_id: str) -> OfficialChunkSnapshot:
    chunk = Chunk(id=chunk_id, text=text, metadata=_metadata())  # type: ignore[arg-type]
    return OfficialChunkSnapshot("official", (chunk,), 1, snapshot_id, "2026-11-25T00:00:00Z")


class MutableLoader:
    collection_name = "official"

    def __init__(self, value):
        self.value = value

    def load(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class BM25IndexManagerTests(unittest.TestCase):
    def _request(self, query):
        return SearchRequest(query, SearchFilter(KnowledgeScope.OFFICIAL))

    def test_initial_build_and_successful_atomic_replacement(self) -> None:
        loader = MutableLoader(_snapshot("old", "쿠폰 안내", "snapshot-old"))
        manager = BM25IndexManager(loader)
        first = manager.rebuild()
        self.assertEqual(first.state, "ready")
        self.assertTrue(first.ids_verified)
        self.assertEqual(first.collection_chunk_count, 1)
        self.assertEqual([hit.chunk_id for hit in manager.search(self._request("쿠폰")).hits], ["old"])

        loader.value = _snapshot("new", "배송 안내", "snapshot-new")
        second = manager.rebuild()
        self.assertEqual(second.snapshot_id, "snapshot-new")
        self.assertEqual([hit.chunk_id for hit in manager.search(self._request("배송")).hits], ["new"])
        self.assertEqual(tuple(manager.search(self._request("쿠폰")).hits), ())

    def test_failed_rebuild_is_fail_closed_and_records_last_success(self) -> None:
        loader = MutableLoader(_snapshot("old", "쿠폰", "snapshot-old"))
        manager = BM25IndexManager(loader)
        manager.rebuild()
        loader.value = BM25ChunkLoadError("broken page")

        with self.assertRaises(BM25ChunkLoadError):
            manager.rebuild()
        self.assertEqual(manager.status.state, "failed")
        self.assertFalse(manager.status.ids_verified)
        self.assertIsNone(manager.status.snapshot_id)
        self.assertEqual(manager.status.last_successful_snapshot_id, "snapshot-old")
        self.assertIn("BM25ChunkLoadError", manager.status.last_error or "")
        with self.assertRaises(BM25IndexUnavailableError):
            manager.search(self._request("쿠폰"))

    def test_rebuild_state_never_exposes_a_partial_index(self) -> None:
        started = threading.Event()
        release = threading.Event()

        class BlockingLoader(MutableLoader):
            def load(self):
                started.set()
                release.wait(timeout=2)
                return self.value

        manager = BM25IndexManager(BlockingLoader(_snapshot("new", "쿠폰", "new")))
        thread = threading.Thread(target=manager.rebuild)
        thread.start()
        self.assertTrue(started.wait(timeout=2))
        self.assertEqual(manager.status.state, "rebuilding")
        with self.assertRaises(BM25IndexUnavailableError):
            manager.search(self._request("쿠폰"))
        with self.assertRaises(BM25RebuildInProgressError):
            manager.rebuild()
        release.set()
        thread.join(timeout=2)
        self.assertEqual(manager.status.state, "ready")

    def test_basic_and_kiwi_tokenizers_are_supported(self) -> None:
        for tokenizer in (basic_tokenize, kiwi_tokenize):
            with self.subTest(tokenizer=tokenizer.__name__):
                manager = BM25IndexManager(
                    MutableLoader(_snapshot("chunk", "쿠폰은 사용 가능합니다", tokenizer.__name__)),
                    tokenizer=tokenizer,
                )
                status = manager.rebuild()
                self.assertEqual(status.tokenizer, tokenizer.__name__)
                self.assertEqual(status.loaded_chunk_count, status.index_chunk_count)


if __name__ == "__main__":
    unittest.main()
