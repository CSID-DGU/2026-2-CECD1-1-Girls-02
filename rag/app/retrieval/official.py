"""Application wiring for approved official-knowledge dense retrieval."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import os
from typing import Any

from .contracts import KnowledgeScope, Retriever, SearchRequest, SearchResponse
from .dense import BgeM3Embedder, ChromaDenseRetriever, Embedder


OFFICIAL_COLLECTION = "brand_a_official_knowledge"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"


class OfficialSearchError(RuntimeError):
    """Base class for failures while preparing or executing official search."""


class OfficialSearchConfigurationError(OfficialSearchError):
    """The environment does not contain a valid retrieval configuration."""


class ChromaConnectionError(OfficialSearchError):
    """The configured Chroma server could not be reached."""


class OfficialCollectionNotFoundError(OfficialSearchError):
    """The official-knowledge collection does not exist in Chroma."""


class OfficialSearchExecutionError(OfficialSearchError):
    """Embedding generation or the Chroma query failed."""


@dataclass(frozen=True, slots=True)
class OfficialSearchSettings:
    host: str = "localhost"
    port: int = 8001
    collection: str = OFFICIAL_COLLECTION
    embedding_model: str = DEFAULT_EMBEDDING_MODEL

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "OfficialSearchSettings":
        values = os.environ if environ is None else environ
        host = values.get("CHROMA_HOST", "localhost").strip()
        collection = values.get("CHROMA_OFFICIAL_COLLECTION", OFFICIAL_COLLECTION).strip()
        embedding_model = values.get("RAG_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip()
        try:
            port = int(values.get("CHROMA_PORT", "8001"))
        except ValueError as exc:
            raise OfficialSearchConfigurationError("CHROMA_PORT must be an integer") from exc
        if not host or not collection or not embedding_model or not 1 <= port <= 65535:
            raise OfficialSearchConfigurationError(
                "Chroma and embedding settings must be non-empty and valid"
            )
        return cls(host=host, port=port, collection=collection, embedding_model=embedding_model)


def _looks_like_not_found(error: Exception) -> bool:
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    return "notfound" in name or "not found" in message or "does not exist" in message


class OfficialKnowledgeSearchService(Retriever):
    """Search only active, approved official knowledge from one Chroma collection."""

    def __init__(self, retriever: ChromaDenseRetriever) -> None:
        self._retriever = retriever

    @classmethod
    def connect(
        cls,
        settings: OfficialSearchSettings | None = None,
        *,
        client_factory: Callable[..., Any] | None = None,
        embedder: Embedder | None = None,
    ) -> "OfficialKnowledgeSearchService":
        settings = settings or OfficialSearchSettings.from_env()
        if client_factory is None:
            try:
                import chromadb  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - deployment dependency
                raise OfficialSearchConfigurationError(
                    "Install chromadb to use official search"
                ) from exc
            client_factory = chromadb.HttpClient

        try:
            client = client_factory(host=settings.host, port=settings.port)
            client.heartbeat()
        except Exception as exc:
            raise ChromaConnectionError(
                f"Could not connect to Chroma at {settings.host}:{settings.port}"
            ) from exc

        try:
            collection = client.get_collection(name=settings.collection)
        except Exception as exc:
            if _looks_like_not_found(exc):
                raise OfficialCollectionNotFoundError(
                    f"Chroma collection does not exist: {settings.collection}"
                ) from exc
            raise ChromaConnectionError(
                f"Could not access Chroma collection: {settings.collection}"
            ) from exc

        actual_embedder = embedder or BgeM3Embedder(model_name=settings.embedding_model)
        return cls(ChromaDenseRetriever(collection, actual_embedder))

    def search(self, request: SearchRequest) -> SearchResponse:
        if request.filters.scope is not KnowledgeScope.OFFICIAL:
            raise ValueError("official search requires scope=official")
        if not request.filters.active_only:
            raise ValueError("official search requires active_only=True")
        try:
            return self._retriever.search(request)
        except Exception as exc:
            raise OfficialSearchExecutionError("Official dense retrieval failed") from exc
