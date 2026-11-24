"""Translate the LangGraph search boundary to the shared RAG retrieval contract."""

from __future__ import annotations

from app.ai.context import RetrievedChunk
from rag.app.retrieval.contracts import (
    KnowledgeScope,
    Retriever,
    SearchFilter,
    SearchHit,
    SearchRequest,
)
from rag.app.retrieval.official import (
    OfficialKnowledgeSearchService,
    OfficialSearchError,
    OfficialSearchSettings,
)


class OfficialRetrievalUnavailable(RuntimeError):
    """Expected RAG-service failure that must prevent automatic answering."""


class OfficialRetrievalAdapter:
    """Expose official RAG search in the form consumed by the LangGraph agent."""

    def __init__(self, service: Retriever) -> None:
        self._service = service

    @classmethod
    def connect(
        cls, settings: OfficialSearchSettings | None = None
    ) -> "OfficialRetrievalAdapter":
        try:
            return cls(OfficialKnowledgeSearchService.connect(settings))
        except OfficialSearchError as error:
            raise OfficialRetrievalUnavailable("Official knowledge retrieval is unavailable") from error

    def search_official(self, query: str, *, top_k: int) -> tuple[RetrievedChunk, ...]:
        request = SearchRequest(
            query=query,
            filters=SearchFilter(scope=KnowledgeScope.OFFICIAL, active_only=True),
            top_k=top_k,
            caller="agent",
        )
        try:
            response = self._service.search(request)
        except OfficialSearchError as error:
            raise OfficialRetrievalUnavailable("Official knowledge retrieval is unavailable") from error
        return tuple(self._to_retrieved_chunk(hit) for hit in response.hits)

    @staticmethod
    def _to_retrieved_chunk(hit: SearchHit) -> RetrievedChunk:
        metadata = dict(hit.metadata)
        metadata.setdefault("document_id", hit.document_id)
        return RetrievedChunk(
            chunk_id=hit.chunk_id,
            text=hit.text,
            score=hit.score,
            metadata=metadata,
        )
