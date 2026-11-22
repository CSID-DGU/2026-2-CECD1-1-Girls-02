"""Public contracts; callers never depend on Chroma or LangChain result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence


class KnowledgeScope(StrEnum):
    OFFICIAL = "official"
    VOC = "voc"


@dataclass(frozen=True, slots=True)
class SearchFilter:
    """Metadata restrictions applied server-side before results are returned."""

    scope: KnowledgeScope
    document_types: tuple[str, ...] = ()
    locales: tuple[str, ...] = ()
    active_only: bool = True

    def __post_init__(self) -> None:
        if self.scope is KnowledgeScope.VOC and not self.active_only:
            raise ValueError("VOC retrieval must not include archived records")


@dataclass(frozen=True, slots=True)
class SearchRequest:
    query: str
    filters: SearchFilter
    top_k: int = 5
    caller: str = "internal"

    def __post_init__(self) -> None:
        if not self.query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= self.top_k <= 50:
            raise ValueError("top_k must be between 1 and 50")
        if self.caller == "chatbot" and self.filters.scope is not KnowledgeScope.OFFICIAL:
            raise PermissionError("chatbot may retrieve official knowledge only")


@dataclass(frozen=True, slots=True)
class SearchHit:
    document_id: str
    chunk_id: str
    text: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SearchResponse:
    hits: Sequence[SearchHit]
    elapsed_ms: float
    strategy: str = "dense"


class Retriever(Protocol):
    def search(self, request: SearchRequest) -> SearchResponse: ...
