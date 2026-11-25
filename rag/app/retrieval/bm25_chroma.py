"""Load approved official Chroma chunks and atomically rebuild BM25 retrieval."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from threading import RLock
from typing import Any, Literal

from ..ingestion import Chunk
from .bm25 import BM25Retriever, Tokenizer, basic_tokenize, build_bm25_index
from .contracts import SearchRequest, SearchResponse
from .official import OfficialSearchSettings


OFFICIAL_CHROMA_WHERE: dict[str, Any] = {
    "$and": [
        {"knowledge_scope": "official"},
        {"is_active": True},
        {"review_status": "APPROVED"},
        {"allowed_use": "DRAFT_ONLY"},
    ]
}
_REQUIRED_IDENTITY_METADATA = ("document_id", "source_id", "document_version", "category")


class BM25ChromaError(RuntimeError):
    """Base class for official Chroma-to-BM25 synchronization failures."""


class BM25ChromaConnectionError(BM25ChromaError):
    """Chroma could not be reached."""


class BM25OfficialCollectionNotFoundError(BM25ChromaError):
    """The configured official collection does not exist."""


class BM25OfficialCollectionEmptyError(BM25ChromaError):
    """The official collection contains no chunks."""


class BM25NoApprovedChunksError(BM25ChromaError):
    """No chunk satisfies the official retrieval policy."""


class BM25ChunkLoadError(BM25ChromaError):
    """Chroma pagination or a stored chunk violates the load contract."""


class BM25CollectionChangedError(BM25ChunkLoadError):
    """The collection count changed while a snapshot was being read."""


class BM25IndexUnavailableError(BM25ChromaError):
    """No successfully verified current BM25 index is available."""


class BM25RebuildInProgressError(BM25ChromaError):
    """A second rebuild was requested while one is already running."""


@dataclass(frozen=True, slots=True)
class OfficialChunkSnapshot:
    collection: str
    chunks: tuple[Chunk, ...]
    collection_count: int
    snapshot_id: str
    loaded_at: str

    @property
    def chunk_ids(self) -> tuple[str, ...]:
        return tuple(chunk.id for chunk in self.chunks)


@dataclass(frozen=True, slots=True)
class BM25SyncStatus:
    state: Literal["empty", "rebuilding", "ready", "failed"] = "empty"
    collection: str = ""
    collection_chunk_count: int = 0
    loaded_chunk_count: int = 0
    index_chunk_count: int = 0
    ids_verified: bool = False
    snapshot_id: str | None = None
    completed_at: str | None = None
    tokenizer: str = ""
    last_error: str | None = None
    last_successful_snapshot_id: str | None = None


def _looks_like_not_found(error: Exception) -> bool:
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    return "notfound" in name or "not found" in message or "does not exist" in message


def _is_approved_official(metadata: dict[str, Any]) -> bool:
    return (
        metadata.get("knowledge_scope") == "official"
        and metadata.get("is_active") is True
        and metadata.get("review_status") == "APPROVED"
        and metadata.get("allowed_use") == "DRAFT_ONLY"
    )


def _snapshot_id(chunks: tuple[Chunk, ...]) -> str:
    digest = sha256()
    for chunk in sorted(chunks, key=lambda item: item.id):
        fields = (
            chunk.id,
            str(chunk.metadata["document_id"]),
            str(chunk.metadata["source_id"]),
            str(chunk.metadata["document_version"]),
            sha256(chunk.text.encode("utf-8")).hexdigest(),
        )
        digest.update("\0".join(fields).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


class OfficialChromaChunkLoader:
    """Read one validated, paginated snapshot from an official collection."""

    def __init__(self, collection: Any, *, collection_name: str, page_size: int = 100) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        self._collection = collection
        self.collection_name = collection_name
        self.page_size = page_size

    @classmethod
    def connect(
        cls,
        settings: OfficialSearchSettings | None = None,
        *,
        page_size: int = 100,
        client_factory: Callable[..., Any] | None = None,
    ) -> "OfficialChromaChunkLoader":
        settings = settings or OfficialSearchSettings.from_env()
        if client_factory is None:
            try:
                import chromadb  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover - deployment dependency
                raise BM25ChromaConnectionError("Install chromadb to load BM25 chunks") from exc
            client_factory = chromadb.HttpClient
        try:
            client = client_factory(host=settings.host, port=settings.port)
            client.heartbeat()
        except Exception as exc:
            raise BM25ChromaConnectionError(
                f"Could not connect to Chroma at {settings.host}:{settings.port}"
            ) from exc
        try:
            collection = client.get_collection(name=settings.collection)
        except Exception as exc:
            if _looks_like_not_found(exc):
                raise BM25OfficialCollectionNotFoundError(
                    f"Chroma collection does not exist: {settings.collection}"
                ) from exc
            raise BM25ChromaConnectionError(
                f"Could not access Chroma collection: {settings.collection}"
            ) from exc
        return cls(collection, collection_name=settings.collection, page_size=page_size)

    def load(self) -> OfficialChunkSnapshot:
        try:
            count_before = int(self._collection.count())
        except Exception as exc:
            raise BM25ChunkLoadError("Could not read Chroma collection count") from exc
        if count_before == 0:
            raise BM25OfficialCollectionEmptyError(
                f"Official collection is empty: {self.collection_name}"
            )

        chunks: list[Chunk] = []
        seen_ids: set[str] = set()
        offset = 0
        while True:
            try:
                page = self._collection.get(
                    where=OFFICIAL_CHROMA_WHERE,
                    limit=self.page_size,
                    offset=offset,
                    include=["documents", "metadatas"],
                )
            except Exception as exc:
                raise BM25ChunkLoadError(
                    f"Could not read Chroma page at offset {offset}"
                ) from exc
            ids = page.get("ids", [])
            documents = page.get("documents", [])
            metadatas = page.get("metadatas", [])
            if not isinstance(ids, list) or not isinstance(documents, list) or not isinstance(metadatas, list):
                raise BM25ChunkLoadError("Chroma page fields must be lists")
            if not (len(ids) == len(documents) == len(metadatas)):
                raise BM25ChunkLoadError("Chroma page fields have different lengths")
            for chunk_id, text, metadata in zip(ids, documents, metadatas, strict=True):
                if not isinstance(chunk_id, str) or not chunk_id.strip():
                    raise BM25ChunkLoadError("Chroma chunk ID must be a non-empty string")
                if chunk_id in seen_ids:
                    raise BM25ChunkLoadError(f"Duplicate Chroma chunk ID: {chunk_id}")
                seen_ids.add(chunk_id)
                if not isinstance(text, str) or not text.strip():
                    raise BM25ChunkLoadError(f"Missing Chroma document text: {chunk_id}")
                if not isinstance(metadata, dict):
                    raise BM25ChunkLoadError(f"Missing Chroma metadata: {chunk_id}")
                if not _is_approved_official(metadata):
                    continue
                missing = [
                    key
                    for key in _REQUIRED_IDENTITY_METADATA
                    if not isinstance(metadata.get(key), str) or not str(metadata[key]).strip()
                ]
                if missing:
                    raise BM25ChunkLoadError(
                        f"Missing required metadata for {chunk_id}: {', '.join(missing)}"
                    )
                chunks.append(
                    Chunk(id=chunk_id, text=text, metadata=dict(metadata))  # type: ignore[arg-type]
                )
            if len(ids) < self.page_size:
                break
            offset += len(ids)

        try:
            count_after = int(self._collection.count())
        except Exception as exc:
            raise BM25ChunkLoadError("Could not verify Chroma collection count") from exc
        if count_after != count_before:
            raise BM25CollectionChangedError(
                f"Collection changed during load: {count_before} -> {count_after}"
            )
        if not chunks:
            raise BM25NoApprovedChunksError(
                f"No approved official chunks found in: {self.collection_name}"
            )
        snapshot_chunks = tuple(chunks)
        return OfficialChunkSnapshot(
            collection=self.collection_name,
            chunks=snapshot_chunks,
            collection_count=count_after,
            snapshot_id=_snapshot_id(snapshot_chunks),
            loaded_at=datetime.now(UTC).isoformat(),
        )


class BM25IndexManager:
    """Fail-closed owner that swaps a completely built retriever atomically."""

    def __init__(self, loader: OfficialChromaChunkLoader, *, tokenizer: Tokenizer = basic_tokenize) -> None:
        if not callable(tokenizer):
            raise TypeError("tokenizer must be callable")
        self._loader = loader
        self._tokenizer = tokenizer
        self._retriever: BM25Retriever | None = None
        self._lock = RLock()
        self._status = BM25SyncStatus(
            collection=loader.collection_name, tokenizer=getattr(tokenizer, "__name__", type(tokenizer).__name__)
        )

    @property
    def status(self) -> BM25SyncStatus:
        with self._lock:
            return self._status

    def rebuild(self) -> BM25SyncStatus:
        with self._lock:
            if self._status.state == "rebuilding":
                raise BM25RebuildInProgressError("BM25 rebuild is already in progress")
            self._status = replace(
                self._status,
                state="rebuilding",
                collection_chunk_count=0,
                loaded_chunk_count=0,
                index_chunk_count=0,
                ids_verified=False,
                snapshot_id=None,
                completed_at=None,
                last_error=None,
            )

        try:
            snapshot = self._loader.load()
            index = build_bm25_index(snapshot.chunks, tokenizer=self._tokenizer)
            if len(index) != len(snapshot.chunks) or tuple(chunk.id for chunk in index.chunks) != snapshot.chunk_ids:
                raise BM25ChunkLoadError("BM25 index IDs do not match the Chroma snapshot")
            retriever = BM25Retriever(index)
        except Exception as exc:
            with self._lock:
                self._status = replace(
                    self._status,
                    state="failed",
                    last_error=f"{type(exc).__name__}: {exc}",
                    completed_at=datetime.now(UTC).isoformat(),
                )
            raise

        with self._lock:
            self._retriever = retriever
            self._status = BM25SyncStatus(
                state="ready",
                collection=snapshot.collection,
                collection_chunk_count=snapshot.collection_count,
                loaded_chunk_count=len(snapshot.chunks),
                index_chunk_count=len(index),
                ids_verified=True,
                snapshot_id=snapshot.snapshot_id,
                completed_at=datetime.now(UTC).isoformat(),
                tokenizer=getattr(self._tokenizer, "__name__", type(self._tokenizer).__name__),
                last_successful_snapshot_id=snapshot.snapshot_id,
            )
            return self._status

    def search(self, request: SearchRequest) -> SearchResponse:
        with self._lock:
            if self._status.state != "ready" or self._retriever is None:
                raise BM25IndexUnavailableError(
                    f"BM25 index is not ready; synchronization state={self._status.state}"
                )
            retriever = self._retriever
        return retriever.search(request)
