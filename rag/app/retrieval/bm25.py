"""In-memory BM25 index construction over ingestion chunks.

Top-K retrieval is intentionally deferred.  This module only owns the minimal
tokenization seam, index construction, and a Retriever-compatible shell.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
import math
from types import MappingProxyType
import re
from time import perf_counter
from typing import Any

from rank_bm25 import BM25Okapi

from ..ingestion import Chunk
from .contracts import KnowledgeScope, Retriever, SearchFilter, SearchHit, SearchRequest, SearchResponse


Tokenizer = Callable[[str], Sequence[str]]
_BASIC_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")


def basic_tokenize(text: str) -> tuple[str, ...]:
    """Apply minimal case-folding and word extraction without Korean analysis."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return tuple(token.casefold() for token in _BASIC_TOKEN.findall(text))


# Keep content-bearing morphemes while dropping particles, endings, and symbols.
# VX is deliberately retained so Korean negation such as 않/못 remains searchable.
_KIWI_CONTENT_TAG_PREFIXES = ("N", "V", "M", "XR", "XSN", "XSV", "XSA", "SL", "SH", "SN")


@lru_cache(maxsize=1)
def _get_kiwi() -> Any:
    """Lazily create one analyzer so basic/Dense imports do not require Kiwi."""
    try:
        from kiwipiepy import Kiwi
    except ImportError as exc:  # pragma: no cover - exercised in minimal deployments
        raise RuntimeError("Install kiwipiepy to use Kiwi BM25 tokenization") from exc
    return Kiwi()


def kiwi_tokenize(text: str) -> tuple[str, ...]:
    """Return normalized content morphemes using one cached Kiwi analyzer."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        return ()
    return tuple(
        token.form.casefold()
        for token in _get_kiwi().tokenize(text)
        if token.form.strip() and token.tag.startswith(_KIWI_CONTENT_TAG_PREFIXES)
    )


@dataclass(frozen=True, slots=True)
class BM25Index:
    """An in-memory BM25 index retaining each source ingestion chunk."""

    chunks: tuple[Chunk, ...]
    tokenized_corpus: tuple[tuple[str, ...], ...]
    tokenizer: Tokenizer = field(repr=False, compare=False)
    _engine: BM25Okapi = field(repr=False, compare=False)
    _positions: Mapping[str, int] = field(repr=False, compare=False)

    def __len__(self) -> int:
        return len(self.chunks)

    def get_chunk(self, chunk_id: str) -> Chunk:
        """Return the original chunk associated with an indexed identifier."""
        try:
            return self.chunks[self._positions[chunk_id]]
        except KeyError as exc:
            raise KeyError(f"unknown chunk id: {chunk_id}") from exc


def build_bm25_index(
    chunks: Iterable[Chunk], *, tokenizer: Tokenizer = basic_tokenize
) -> BM25Index:
    """Build a BM25Okapi index without changing chunks or external storage."""
    if isinstance(chunks, (str, bytes)):
        raise TypeError("chunks must be an iterable of Chunk objects")
    try:
        source_chunks = tuple(chunks)
    except TypeError as exc:
        raise TypeError("chunks must be an iterable of Chunk objects") from exc
    if not source_chunks:
        raise ValueError("at least one chunk is required")
    if not callable(tokenizer):
        raise TypeError("tokenizer must be callable")

    positions: dict[str, int] = {}
    corpus: list[tuple[str, ...]] = []
    for position, chunk in enumerate(source_chunks):
        if not isinstance(chunk, Chunk):
            raise TypeError("every indexed item must be an ingestion Chunk")
        if not chunk.id.strip():
            raise ValueError("chunk id must not be empty")
        if chunk.id in positions:
            raise ValueError(f"duplicate chunk id: {chunk.id}")
        if not chunk.text.strip():
            raise ValueError(f"chunk text must not be empty: {chunk.id}")
        if not isinstance(chunk.metadata, dict):
            raise TypeError(f"chunk metadata must be a dict: {chunk.id}")

        raw_tokens = tokenizer(chunk.text)
        if isinstance(raw_tokens, (str, bytes)):
            raise TypeError("tokenizer must return a sequence of token strings")
        tokens = tuple(raw_tokens)
        if not tokens or any(not isinstance(token, str) or not token for token in tokens):
            raise ValueError(f"tokenizer produced no valid tokens: {chunk.id}")
        positions[chunk.id] = position
        corpus.append(tokens)

    tokenized_corpus = tuple(corpus)
    engine = BM25Okapi([list(tokens) for tokens in tokenized_corpus])
    return BM25Index(
        chunks=source_chunks,
        tokenized_corpus=tokenized_corpus,
        tokenizer=tokenizer,
        _engine=engine,
        _positions=MappingProxyType(positions),
    )


def _matches_filter(metadata: Mapping[str, Any], filters: SearchFilter) -> bool:
    """Apply the allow-listed SearchFilter without widening on missing metadata."""
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


class BM25Retriever(Retriever):
    """Top-K keyword retrieval over an immutable in-memory BM25 index."""

    def __init__(self, index: BM25Index) -> None:
        if not isinstance(index, BM25Index):
            raise TypeError("index must be a BM25Index")
        self.index = index

    def search(self, request: SearchRequest) -> SearchResponse:
        started = perf_counter()
        if request.filters.scope is KnowledgeScope.OFFICIAL and not request.filters.active_only:
            raise ValueError("official BM25 search requires active_only=True")

        raw_query_tokens = self.index.tokenizer(request.query)
        if isinstance(raw_query_tokens, (str, bytes)):
            raise TypeError("tokenizer must return a sequence of token strings")
        query_tokens = tuple(raw_query_tokens)
        if any(not isinstance(token, str) or not token for token in query_tokens):
            raise TypeError("tokenizer returned an invalid query token")
        if not query_tokens:
            return SearchResponse(
                hits=(), elapsed_ms=(perf_counter() - started) * 1000, strategy="bm25"
            )

        scores = self.index._engine.get_scores(list(query_tokens))
        if len(scores) != len(self.index.chunks):
            raise RuntimeError("BM25 score count does not match indexed chunks")

        query_vocabulary = set(query_tokens)
        candidates: list[tuple[float, Chunk]] = []
        for chunk, document_tokens, raw_score in zip(
            self.index.chunks, self.index.tokenized_corpus, scores, strict=True
        ):
            if not _matches_filter(chunk.metadata, request.filters):
                continue
            # A zero or negative BM25 score can still represent a lexical match;
            # documents with no shared token are never used merely to fill top_k.
            if query_vocabulary.isdisjoint(document_tokens):
                continue
            score = float(raw_score)
            if not math.isfinite(score):
                raise RuntimeError(f"BM25 returned a non-finite score for chunk: {chunk.id}")
            candidates.append((score, chunk))

        candidates.sort(key=lambda item: (-item[0], item[1].id))
        hits = tuple(
            SearchHit(
                document_id=str(chunk.metadata.get("document_id", chunk.id)),
                chunk_id=chunk.id,
                text=chunk.text,
                score=score,
                metadata=dict(chunk.metadata),
            )
            for score, chunk in candidates[: request.top_k]
        )
        return SearchResponse(
            hits=hits, elapsed_ms=(perf_counter() - started) * 1000, strategy="bm25"
        )
