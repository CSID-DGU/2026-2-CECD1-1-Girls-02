"""Rank-only fusion of existing Dense and BM25 retrieval results."""

from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from typing import Any, Mapping, Sequence

from .contracts import (
    KnowledgeScope,
    Retriever,
    SearchFilter,
    SearchHit,
    SearchRequest,
    SearchResponse,
)


DEFAULT_RRF_K = 60
DEFAULT_CANDIDATE_K = 10
_CONSISTENCY_METADATA = (
    "document_version",
    "knowledge_scope",
    "is_active",
    "review_status",
    "allowed_use",
)


class HybridRetrievalError(RuntimeError):
    """Base class for fusion failures after child retrieval succeeds."""


class HybridDuplicateChunkError(HybridRetrievalError):
    """One child retriever returned the same chunk ID more than once."""


class HybridResultConflictError(HybridRetrievalError):
    """Dense and BM25 disagree about the identity or content of one chunk."""


def reciprocal_rank_score(rank: int, *, rrf_k: int = DEFAULT_RRF_K) -> float:
    """Return one standard RRF contribution for a one-based rank."""
    if rank < 1:
        raise ValueError("rank must be at least 1")
    if rrf_k < 1:
        raise ValueError("rrf_k must be at least 1")
    return 1.0 / (rrf_k + rank)


def _unique_hits(hits: Sequence[SearchHit], source: str) -> tuple[SearchHit, ...]:
    seen: set[str] = set()
    unique: list[SearchHit] = []
    for hit in hits:
        if not hit.chunk_id:
            raise HybridDuplicateChunkError(f"{source} returned an empty chunk_id")
        if hit.chunk_id in seen:
            raise HybridDuplicateChunkError(
                f"{source} returned duplicate chunk_id: {hit.chunk_id}"
            )
        seen.add(hit.chunk_id)
        unique.append(hit)
    return tuple(unique)


def _validate_same_chunk(dense: SearchHit, bm25: SearchHit) -> None:
    if dense.document_id != bm25.document_id:
        raise HybridResultConflictError(
            f"document_id mismatch for chunk_id={dense.chunk_id}"
        )
    if dense.text != bm25.text:
        raise HybridResultConflictError(f"text mismatch for chunk_id={dense.chunk_id}")
    for key in _CONSISTENCY_METADATA:
        if dense.metadata.get(key) != bm25.metadata.get(key):
            raise HybridResultConflictError(
                f"metadata mismatch for chunk_id={dense.chunk_id}: {key}"
            )


def _matches_filter(metadata: Mapping[str, Any], filters: SearchFilter) -> bool:
    """Defence in depth after both child retrievers apply the same filter."""
    if metadata.get("knowledge_scope") != filters.scope.value:
        return False
    if filters.active_only and metadata.get("is_active") is not True:
        return False
    if filters.scope is KnowledgeScope.OFFICIAL and (
        metadata.get("review_status") != "APPROVED"
        or metadata.get("allowed_use") != "DRAFT_ONLY"
    ):
        return False
    if filters.document_types and metadata.get("document_type") not in filters.document_types:
        return False
    if filters.locales and metadata.get("locale") not in filters.locales:
        return False
    return True


class HybridRetriever(Retriever):
    """Fuse Dense and BM25 rankings with equal-weight reciprocal rank fusion."""

    def __init__(
        self,
        dense: Retriever,
        bm25: Retriever,
        *,
        rrf_k: int = DEFAULT_RRF_K,
        dense_candidate_k: int = DEFAULT_CANDIDATE_K,
        bm25_candidate_k: int = DEFAULT_CANDIDATE_K,
    ) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1")
        if not 1 <= dense_candidate_k <= 50 or not 1 <= bm25_candidate_k <= 50:
            raise ValueError("candidate counts must be between 1 and 50")
        self._dense = dense
        self._bm25 = bm25
        self.rrf_k = rrf_k
        self.dense_candidate_k = dense_candidate_k
        self.bm25_candidate_k = bm25_candidate_k

    def search(self, request: SearchRequest) -> SearchResponse:
        started = perf_counter()
        if request.filters.scope is KnowledgeScope.OFFICIAL and not request.filters.active_only:
            raise ValueError("official hybrid search requires active_only=True")
        dense_request = replace(
            request, top_k=min(50, max(request.top_k, self.dense_candidate_k))
        )
        bm25_request = replace(
            request, top_k=min(50, max(request.top_k, self.bm25_candidate_k))
        )

        # Child failures deliberately propagate; an error is not an empty ranking.
        dense_hits = _unique_hits(self._dense.search(dense_request).hits, "dense")
        bm25_hits = _unique_hits(self._bm25.search(bm25_request).hits, "bm25")

        dense_by_id = {hit.chunk_id: hit for hit in dense_hits}
        bm25_by_id = {hit.chunk_id: hit for hit in bm25_hits}
        for chunk_id in dense_by_id.keys() & bm25_by_id.keys():
            _validate_same_chunk(dense_by_id[chunk_id], bm25_by_id[chunk_id])

        safe_dense = tuple(hit for hit in dense_hits if _matches_filter(hit.metadata, request.filters))
        safe_bm25 = tuple(hit for hit in bm25_hits if _matches_filter(hit.metadata, request.filters))
        scores: dict[str, float] = {}
        selected: dict[str, SearchHit] = {}
        for hits in (safe_dense, safe_bm25):
            for rank, hit in enumerate(hits, start=1):
                scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + reciprocal_rank_score(
                    rank, rrf_k=self.rrf_k
                )
                selected.setdefault(hit.chunk_id, hit)

        ranked_ids = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
        final_hits = tuple(
            SearchHit(
                document_id=selected[chunk_id].document_id,
                chunk_id=chunk_id,
                text=selected[chunk_id].text,
                score=scores[chunk_id],
                metadata=dict(selected[chunk_id].metadata),
            )
            for chunk_id in ranked_ids[: request.top_k]
        )
        return SearchResponse(
            hits=final_hits,
            elapsed_ms=(perf_counter() - started) * 1000,
            strategy="hybrid_rrf",
        )
