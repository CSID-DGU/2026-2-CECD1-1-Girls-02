"""BGE-M3 + Chroma dense-retrieval baseline."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol, Sequence

from .contracts import Retriever, SearchHit, SearchRequest, SearchResponse
from .filters import chroma_where


class Embedder(Protocol):
    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


class BgeM3Embedder:
    """Lazy BGE-M3 adapter, keeping the core retriever free of ML dependencies."""

    def __init__(self, model_name: str = "BAAI/bge-m3", use_fp16: bool | None = None) -> None:
        self.model_name = model_name
        self.use_fp16 = use_fp16
        self._model: Any | None = None

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        if self._model is None:
            try:
                from FlagEmbedding import BGEM3FlagModel
                import torch
            except ImportError as exc:  # pragma: no cover - deployment dependency
                raise RuntimeError("Install FlagEmbedding to use BGE-M3") from exc
            use_fp16 = torch.cuda.is_available() if self.use_fp16 is None else self.use_fp16
            self._model = BGEM3FlagModel(self.model_name, use_fp16=use_fp16)
        return self._model.encode(list(texts), return_dense=True)["dense_vecs"]


class ChromaDenseRetriever(Retriever):
    """Adapter around a Chroma collection compatible with collection.query()."""

    def __init__(self, collection: Any, embedder: Embedder) -> None:
        self._collection = collection
        self._embedder = embedder

    def search(self, request: SearchRequest) -> SearchResponse:
        started = perf_counter()
        vector = self._embedder.encode([request.query])[0]
        raw = self._collection.query(
            query_embeddings=[vector], n_results=request.top_k,
            where=chroma_where(request.filters),
            include=["documents", "metadatas", "distances"],
        )
        documents = raw.get("documents", [[]])[0] or []
        metadata = raw.get("metadatas", [[]])[0] or []
        distances = raw.get("distances", [[]])[0] or []
        ids = raw.get("ids", [[]])[0] or []
        hits = tuple(
            SearchHit(
                document_id=str(meta.get("document_id", chunk_id)), chunk_id=str(chunk_id),
                text=str(text), score=1.0 / (1.0 + float(distance)), metadata=dict(meta),
            )
            for chunk_id, text, meta, distance in zip(ids, documents, metadata, distances, strict=True)
        )
        return SearchResponse(hits=hits, elapsed_ms=(perf_counter() - started) * 1000)
