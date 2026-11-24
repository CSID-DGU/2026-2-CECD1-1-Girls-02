"""Composition root for the real RAG Agent dependencies.

The API layer owns when this factory is called.  Keeping construction here
lets FastAPI inject a fully configured graph without teaching route handlers
about Chroma, embeddings, or Ollama.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.ai.agent import build_rag_agent_graph
from app.ai.ollama import OllamaClient
from app.ai.orchestrator import DraftOrchestrator
from app.ai.retrieval_adapter import OfficialRetrievalAdapter
from app.core.config import Settings
from rag.app.retrieval.official import OfficialSearchSettings


@dataclass(frozen=True)
class RagAgentRuntime:
    """Dependencies and compiled graph supplied to the application service."""

    search: OfficialRetrievalAdapter
    orchestrator: DraftOrchestrator
    graph: Any


def build_rag_agent_runtime(settings: Settings) -> RagAgentRuntime:
    """Create the production graph from application configuration.

    This intentionally connects only when the inquiry service requests the
    runtime; app startup and the liveness endpoint stay available during a
    Chroma outage.
    """
    search = OfficialRetrievalAdapter.connect(
        OfficialSearchSettings(
            host=settings.chroma_host,
            port=settings.chroma_port,
            collection=settings.chroma_official_collection,
            embedding_model=settings.rag_embedding_model,
        )
    )
    orchestrator = DraftOrchestrator(
        OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
    )
    graph = build_rag_agent_graph(
        search=search,
        orchestrator=orchestrator,
        top_k=settings.rag_top_k,
    )
    return RagAgentRuntime(search=search, orchestrator=orchestrator, graph=graph)


@lru_cache
def get_rag_agent_runtime() -> RagAgentRuntime:
    """Lazily construct the runtime for FastAPI dependency injection."""
    from app.core.config import get_settings

    return build_rag_agent_runtime(get_settings())
