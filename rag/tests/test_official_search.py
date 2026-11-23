from __future__ import annotations

import unittest

from rag.app.retrieval.contracts import KnowledgeScope, SearchFilter, SearchRequest
from rag.app.retrieval.official import (
    ChromaConnectionError,
    OfficialCollectionNotFoundError,
    OfficialKnowledgeSearchService,
    OfficialSearchSettings,
)


class FakeEmbedder:
    def encode(self, texts):
        return [[0.1, 0.2] for _ in texts]


class FakeCollection:
    def __init__(self, response=None):
        self.response = response or {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    def query(self, **kwargs):
        self.query_kwargs = kwargs
        return self.response


class FakeClient:
    def __init__(self, collection):
        self.collection = collection

    def heartbeat(self):
        return 1

    def get_collection(self, *, name):
        self.collection_name = name
        return self.collection


def _request() -> SearchRequest:
    return SearchRequest(
        "쿠폰 사용 방법", SearchFilter(scope=KnowledgeScope.OFFICIAL), top_k=3
    )


class OfficialSearchTests(unittest.TestCase):
    def test_settings_read_local_and_container_chroma_addresses(self) -> None:
        self.assertEqual(OfficialSearchSettings.from_env({}), OfficialSearchSettings())
        settings = OfficialSearchSettings.from_env(
            {"CHROMA_HOST": "chroma", "CHROMA_PORT": "8000"}
        )
        self.assertEqual((settings.host, settings.port), ("chroma", 8000))

    def test_connects_to_configured_collection_and_preserves_contract(self) -> None:
        collection = FakeCollection(
            {
                "ids": [["chunk-1"]],
                "documents": [["공식 쿠폰 안내"]],
                "metadatas": [[{"document_id": "faq:1", "source_id": "faq:1"}]],
                "distances": [[0.25]],
            }
        )
        client = FakeClient(collection)
        service = OfficialKnowledgeSearchService.connect(
            client_factory=lambda **kwargs: client,
            embedder=FakeEmbedder(),
        )

        response = service.search(_request())

        self.assertEqual(client.collection_name, "brand_a_official_knowledge")
        self.assertEqual(response.hits[0].chunk_id, "chunk-1")
        self.assertEqual(response.hits[0].text, "공식 쿠폰 안내")
        self.assertEqual(response.hits[0].metadata["source_id"], "faq:1")
        self.assertEqual(collection.query_kwargs["n_results"], 3)
        self.assertEqual(
            collection.query_kwargs["where"],
            {
                "$and": [
                    {"knowledge_scope": "official"},
                    {"is_active": True},
                    {"review_status": "APPROVED"},
                    {"allowed_use": "DRAFT_ONLY"},
                ]
            },
        )

    def test_empty_collection_result_is_a_successful_empty_response(self) -> None:
        service = OfficialKnowledgeSearchService.connect(
            client_factory=lambda **kwargs: FakeClient(FakeCollection()),
            embedder=FakeEmbedder(),
        )
        self.assertEqual(tuple(service.search(_request()).hits), ())

    def test_connection_failure_is_distinct_from_missing_collection(self) -> None:
        def disconnected(**kwargs):
            raise OSError("connection refused")

        with self.assertRaises(ChromaConnectionError):
            OfficialKnowledgeSearchService.connect(
                client_factory=disconnected, embedder=FakeEmbedder()
            )

        class NotFoundError(Exception):
            pass

        class MissingCollectionClient(FakeClient):
            def get_collection(self, *, name):
                raise NotFoundError("collection not found")

        with self.assertRaises(OfficialCollectionNotFoundError):
            OfficialKnowledgeSearchService.connect(
                client_factory=lambda **kwargs: MissingCollectionClient(None),
                embedder=FakeEmbedder(),
            )

    def test_rejects_voc_or_inactive_requests(self) -> None:
        service = OfficialKnowledgeSearchService.connect(
            client_factory=lambda **kwargs: FakeClient(FakeCollection()),
            embedder=FakeEmbedder(),
        )
        with self.assertRaisesRegex(ValueError, "scope=official"):
            service.search(SearchRequest("case", SearchFilter(scope=KnowledgeScope.VOC)))
        with self.assertRaisesRegex(ValueError, "active_only=True"):
            service.search(
                SearchRequest("old", SearchFilter(scope=KnowledgeScope.OFFICIAL, active_only=False))
            )
