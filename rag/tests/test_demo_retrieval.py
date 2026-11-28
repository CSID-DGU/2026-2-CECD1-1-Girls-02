"""Check demo rendering against the real RRF implementation."""

from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

from rag.app.retrieval.contracts import SearchHit, SearchRequest, SearchResponse
from rag.app.retrieval.hybrid import HybridRetriever
from rag.scripts.demo_retrieval import FILTER, ObservedRetriever, emit_results, preview, rrf_details


class FixedRetriever:
    def __init__(self, *chunk_ids: str):
        self.chunk_ids = chunk_ids

    def search(self, request: SearchRequest) -> SearchResponse:
        metadata = {
            "title": "테스트 문서", "source_id": "source-test",
            "knowledge_scope": "official", "is_active": True,
            "review_status": "APPROVED", "allowed_use": "DRAFT_ONLY",
        }
        return SearchResponse(tuple(
            SearchHit("shared-doc", chunk_id, "예시 본문", 9, metadata)
            for chunk_id in self.chunk_ids[:request.top_k]
        ), 1.2)


class DemoRetrievalTest(unittest.TestCase):
    @patch("rag.scripts.demo_retrieval.display_text", side_effect=str)
    def test_output_uses_real_rrf_ranks_by_chunk_id(self, _display):
        dense = ObservedRetriever(FixedRetriever("dense-only", "shared-chunk"))
        bm25 = ObservedRetriever(FixedRetriever("shared-chunk", "bm25-only"))
        response = HybridRetriever(dense, bm25).search(SearchRequest("질문", FILTER))
        output = StringIO()
        with redirect_stdout(output):
            emit_results("HYBRID RRF", 5, response, False,
                         (dense.captured(), bm25.captured()))
        text = output.getvalue()
        self.assertIn("[HYBRID RRF TOP-5] 3개", text)
        self.assertIn("chunk_id: shared-chunk", text)
        self.assertIn("source_id: source-test", text)
        self.assertIn("Dense 순위: 2 | BM25 순위: 1", text)
        self.assertIn("1 / (60 + 2) + 1 / (60 + 1) = 0.03252247 (일치)", text)
        self.assertIn("Dense 순위: 1 | BM25 순위: 후보 없음", text)
        self.assertIn("Dense 순위: 후보 없음 | BM25 순위: 2", text)

    def test_rejects_score_that_does_not_match_observed_ranks(self):
        with self.assertRaisesRegex(RuntimeError, "일치하지 않습니다"):
            rrf_details("a", 1, {"a": 1}, {})

    @patch("rag.scripts.demo_retrieval.display_text", side_effect=str)
    def test_preview_includes_ellipsis_within_limit_and_can_show_full_text(self, _display):
        body = "가" * 201
        self.assertEqual(preview(body, False), "가" * 199 + "…")
        self.assertEqual(preview(body, True), body)
