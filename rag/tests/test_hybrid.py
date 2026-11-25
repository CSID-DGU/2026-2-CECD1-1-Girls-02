from __future__ import annotations

import unittest

from rag.app.retrieval.bm25_chroma import BM25IndexUnavailableError
from rag.app.retrieval.contracts import (
    KnowledgeScope,
    SearchFilter,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from rag.app.retrieval.hybrid import (
    HybridDuplicateChunkError,
    HybridResultConflictError,
    HybridRetriever,
    reciprocal_rank_score,
)


def _metadata(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "document_version": "v1",
        "knowledge_scope": "official",
        "is_active": True,
        "review_status": "APPROVED",
        "allowed_use": "DRAFT_ONLY",
        "document_type": "FAQ",
        "locale": "ko-KR",
    }
    value.update(overrides)
    return value


def _hit(chunk_id: str, *, score: float = 0.0, text: str | None = None, **metadata: object) -> SearchHit:
    return SearchHit(
        document_id=f"document-{chunk_id}",
        chunk_id=chunk_id,
        text=text or f"text-{chunk_id}",
        score=score,
        metadata=_metadata(**metadata),
    )


class FakeRetriever:
    def __init__(self, hits=(), error: Exception | None = None):
        self.hits = tuple(hits)
        self.error = error
        self.requests: list[SearchRequest] = []

    def search(self, request: SearchRequest) -> SearchResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        return SearchResponse(self.hits, elapsed_ms=1.0, strategy="fake")


def _request(top_k: int = 5) -> SearchRequest:
    return SearchRequest("쿠폰", SearchFilter(KnowledgeScope.OFFICIAL), top_k=top_k)


class ReciprocalRankFusionTests(unittest.TestCase):
    def test_standard_rrf_formula_uses_one_based_rank(self) -> None:
        self.assertAlmostEqual(reciprocal_rank_score(1), 1 / 61)
        self.assertAlmostEqual(reciprocal_rank_score(2, rrf_k=10), 1 / 12)
        with self.assertRaises(ValueError):
            reciprocal_rank_score(0)

    def test_shared_chunk_sums_ranks_and_original_scores_are_ignored(self) -> None:
        dense = FakeRetriever([_hit("a", score=999), _hit("shared", score=-999)])
        bm25 = FakeRetriever([_hit("shared", score=0), _hit("b", score=10000)])

        response = HybridRetriever(dense, bm25).search(_request())

        self.assertEqual([hit.chunk_id for hit in response.hits], ["shared", "a", "b"])
        self.assertAlmostEqual(response.hits[0].score, 1 / 62 + 1 / 61)
        self.assertAlmostEqual(response.hits[1].score, 1 / 61)
        self.assertAlmostEqual(response.hits[2].score, 1 / 62)
        self.assertEqual(response.strategy, "hybrid_rrf")
        self.assertGreaterEqual(response.elapsed_ms, 0)

    def test_equal_rrf_scores_use_chunk_id_and_final_top_k(self) -> None:
        response = HybridRetriever(
            FakeRetriever([_hit("b")]), FakeRetriever([_hit("a")])
        ).search(_request(top_k=1))
        self.assertEqual([hit.chunk_id for hit in response.hits], ["a"])

    def test_candidate_count_is_at_least_final_k_and_never_exceeds_contract(self) -> None:
        for final_k, expected_candidate_k in ((1, 10), (3, 10), (5, 10), (10, 10), (50, 50)):
            with self.subTest(final_k=final_k):
                dense = FakeRetriever()
                bm25 = FakeRetriever()
                HybridRetriever(dense, bm25).search(_request(final_k))
                self.assertEqual(dense.requests[0].top_k, expected_candidate_k)
                self.assertEqual(bm25.requests[0].top_k, expected_candidate_k)
                self.assertIs(dense.requests[0].filters, bm25.requests[0].filters)

    def test_custom_candidate_counts_remain_configurable(self) -> None:
        dense = FakeRetriever()
        bm25 = FakeRetriever()
        HybridRetriever(dense, bm25, dense_candidate_k=7, bm25_candidate_k=12).search(
            _request(3)
        )
        self.assertEqual(dense.requests[0].top_k, 7)
        self.assertEqual(bm25.requests[0].top_k, 12)

    def test_both_empty_and_one_side_empty_are_normal_results(self) -> None:
        empty = HybridRetriever(FakeRetriever(), FakeRetriever()).search(_request())
        dense_only = HybridRetriever(FakeRetriever([_hit("dense")]), FakeRetriever()).search(
            _request()
        )
        bm25_only = HybridRetriever(FakeRetriever(), FakeRetriever([_hit("bm25")])).search(
            _request()
        )
        self.assertEqual(tuple(empty.hits), ())
        self.assertEqual([hit.chunk_id for hit in dense_only.hits], ["dense"])
        self.assertEqual([hit.chunk_id for hit in bm25_only.hits], ["bm25"])


class HybridSafetyTests(unittest.TestCase):
    def test_same_chunk_preserves_fields_and_is_returned_once(self) -> None:
        dense_hit = _hit("same")
        bm25_hit = _hit("same")
        response = HybridRetriever(
            FakeRetriever([dense_hit]), FakeRetriever([bm25_hit])
        ).search(_request())
        self.assertEqual(len(response.hits), 1)
        self.assertEqual(response.hits[0].document_id, dense_hit.document_id)
        self.assertEqual(response.hits[0].text, dense_hit.text)
        self.assertEqual(response.hits[0].metadata, dense_hit.metadata)

    def test_different_chunks_with_same_document_id_are_not_merged(self) -> None:
        first = _hit("chunk-a")
        second = SearchHit(
            document_id=first.document_id,
            chunk_id="chunk-b",
            text="second chunk",
            score=0,
            metadata=_metadata(),
        )
        response = HybridRetriever(
            FakeRetriever([first]), FakeRetriever([second])
        ).search(_request())
        self.assertEqual([hit.chunk_id for hit in response.hits], ["chunk-a", "chunk-b"])

    def test_unique_unsafe_hits_are_excluded_defensively(self) -> None:
        hits = [
            _hit("approved"),
            _hit("pending", review_status="PENDING_REVIEW"),
            _hit("inactive", is_active=False),
            _hit("forbidden", allowed_use="NOT_ALLOWED"),
            _hit("voc", knowledge_scope="voc"),
        ]
        response = HybridRetriever(FakeRetriever(hits), FakeRetriever()).search(_request())
        self.assertEqual([hit.chunk_id for hit in response.hits], ["approved"])

    def test_document_type_and_locale_filters_are_checked_again(self) -> None:
        request = SearchRequest(
            "쿠폰",
            SearchFilter(
                KnowledgeScope.OFFICIAL, document_types=("FAQ",), locales=("ko-KR",)
            ),
        )
        hits = [_hit("ok"), _hit("guide", document_type="GUIDE"), _hit("en", locale="en-US")]
        response = HybridRetriever(FakeRetriever(hits), FakeRetriever()).search(request)
        self.assertEqual([hit.chunk_id for hit in response.hits], ["ok"])

    def test_conflicting_shared_chunk_identity_content_version_or_policy_raises(self) -> None:
        mutations = {
            "document_id": SearchHit("other", "same", "text-same", 0, _metadata()),
            "text": _hit("same", text="different"),
            "document_version": _hit("same", document_version="v2"),
            "policy": _hit("same", review_status="PENDING_REVIEW"),
        }
        for field, bm25_hit in mutations.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(HybridResultConflictError, "mismatch"):
                    HybridRetriever(
                        FakeRetriever([_hit("same")]), FakeRetriever([bm25_hit])
                    ).search(_request())

    def test_duplicate_id_inside_one_child_is_an_error(self) -> None:
        with self.assertRaises(HybridDuplicateChunkError):
            HybridRetriever(
                FakeRetriever([_hit("same"), _hit("same")]), FakeRetriever()
            ).search(_request())

    def test_child_errors_and_unavailable_bm25_are_not_hidden(self) -> None:
        errors = (
            (RuntimeError("dense failed"), None),
            (None, RuntimeError("bm25 failed")),
            (None, BM25IndexUnavailableError("rebuilding")),
        )
        for dense_error, bm25_error in errors:
            with self.subTest(dense=dense_error, bm25=bm25_error):
                with self.assertRaises(type(dense_error or bm25_error)):
                    HybridRetriever(
                        FakeRetriever(error=dense_error), FakeRetriever(error=bm25_error)
                    ).search(_request())

    def test_invalid_configuration_and_request_boundaries_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            HybridRetriever(FakeRetriever(), FakeRetriever(), rrf_k=0)
        with self.assertRaises(ValueError):
            HybridRetriever(FakeRetriever(), FakeRetriever(), dense_candidate_k=51)
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            _request(0)
        inactive_request = SearchRequest(
            "쿠폰", SearchFilter(KnowledgeScope.OFFICIAL, active_only=False)
        )
        with self.assertRaisesRegex(ValueError, "active_only=True"):
            HybridRetriever(FakeRetriever(), FakeRetriever()).search(inactive_request)


if __name__ == "__main__":
    unittest.main()
