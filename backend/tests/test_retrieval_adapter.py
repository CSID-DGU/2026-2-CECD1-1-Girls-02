from __future__ import annotations

import importlib.util
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

if importlib.util.find_spec("httpx") is None:  # Adapter tests do not execute Ollama HTTP calls.
    sys.modules["httpx"] = ModuleType("httpx")

from app.ai.agent import OfficialKnowledgeSearch
from app.ai.retrieval_adapter import OfficialRetrievalAdapter
from rag.app.retrieval.contracts import (
    KnowledgeScope,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from rag.app.retrieval.official import (
    ChromaConnectionError,
    OfficialCollectionNotFoundError,
    OfficialSearchExecutionError,
)


def _hit(document_id: str, chunk_id: str, *, score: float) -> SearchHit:
    return SearchHit(
        document_id=document_id,
        chunk_id=chunk_id,
        text=f"공식 안내 {chunk_id}",
        score=score,
        metadata={
            "source_id": document_id,
            "title": f"FAQ {document_id}",
            "knowledge_scope": "official",
            "is_active": True,
            "review_status": "APPROVED",
            "allowed_use": "DRAFT_ONLY",
        },
    )


class FakeRetrievalService:
    def __init__(
        self, response: SearchResponse | None = None, error: Exception | None = None
    ) -> None:
        self.response = response or SearchResponse(hits=(), elapsed_ms=1.0)
        self.error = error
        self.requests: list[SearchRequest] = []

    def search(self, request: SearchRequest) -> SearchResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.response


def _accepts_agent_protocol(search: OfficialKnowledgeSearch) -> OfficialKnowledgeSearch:
    return search


class OfficialRetrievalAdapterTests(unittest.TestCase):
    def test_builds_official_request_and_forwards_query_and_top_k(self) -> None:
        service = FakeRetrievalService()
        adapter = OfficialRetrievalAdapter(service)

        adapter.search_official("멤버십 혜택", top_k=3)

        request = service.requests[0]
        self.assertEqual(request.query, "멤버십 혜택")
        self.assertEqual(request.top_k, 3)
        self.assertIs(request.filters.scope, KnowledgeScope.OFFICIAL)
        self.assertTrue(request.filters.active_only)
        self.assertEqual(request.caller, "agent")

    def test_converts_hits_in_order_and_preserves_content_and_sources(self) -> None:
        first = _hit("faq:1", "chunk-1", score=0.9)
        second = _hit("faq:2", "chunk-2", score=0.7)
        service = FakeRetrievalService(SearchResponse((first, second), elapsed_ms=4.2))

        chunks = OfficialRetrievalAdapter(service).search_official("쿠폰", top_k=2)

        self.assertEqual([chunk.chunk_id for chunk in chunks], ["chunk-1", "chunk-2"])
        self.assertEqual([chunk.text for chunk in chunks], [first.text, second.text])
        self.assertEqual([chunk.score for chunk in chunks], [0.9, 0.7])
        self.assertEqual(chunks[0].metadata["document_id"], "faq:1")
        self.assertEqual(chunks[0].metadata["source_id"], "faq:1")
        self.assertEqual(chunks[0].metadata["title"], "FAQ faq:1")

    def test_preserves_existing_document_id_metadata(self) -> None:
        hit = _hit("response-document", "chunk-1", score=0.9)
        hit = SearchHit(
            hit.document_id,
            hit.chunk_id,
            hit.text,
            hit.score,
            {**hit.metadata, "document_id": "metadata-document"},
        )
        service = FakeRetrievalService(SearchResponse((hit,), elapsed_ms=1.0))

        chunk = OfficialRetrievalAdapter(service).search_official("질문", top_k=1)[0]

        self.assertEqual(chunk.metadata["document_id"], "metadata-document")

    def test_returns_empty_tuple_for_empty_search_response(self) -> None:
        service = FakeRetrievalService(SearchResponse((), elapsed_ms=1.0))
        self.assertEqual(OfficialRetrievalAdapter(service).search_official("질문", top_k=5), ())

    def test_does_not_hide_retrieval_errors(self) -> None:
        error = OfficialSearchExecutionError("embedding failed")
        service = FakeRetrievalService(error=error)

        with self.assertRaises(OfficialSearchExecutionError) as raised:
            OfficialRetrievalAdapter(service).search_official("질문", top_k=5)

        self.assertIs(raised.exception, error)

    def test_connect_does_not_hide_connection_or_collection_errors(self) -> None:
        errors = (
            ChromaConnectionError("connection failed"),
            OfficialCollectionNotFoundError("collection missing"),
        )
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch(
                    "app.ai.retrieval_adapter.OfficialKnowledgeSearchService.connect",
                    side_effect=error,
                ):
                    with self.assertRaises(type(error)) as raised:
                        OfficialRetrievalAdapter.connect()
                self.assertIs(raised.exception, error)

    def test_invalid_input_is_rejected_by_existing_search_request_contract(self) -> None:
        adapter = OfficialRetrievalAdapter(FakeRetrievalService())
        with self.assertRaisesRegex(ValueError, "query must not be empty"):
            adapter.search_official("   ", top_k=5)
        with self.assertRaisesRegex(ValueError, "top_k must be between"):
            adapter.search_official("질문", top_k=0)

    def test_matches_agent_search_protocol(self) -> None:
        adapter = OfficialRetrievalAdapter(FakeRetrievalService())
        self.assertIs(_accepts_agent_protocol(adapter), adapter)
