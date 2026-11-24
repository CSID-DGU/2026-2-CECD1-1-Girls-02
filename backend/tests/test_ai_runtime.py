from unittest.mock import patch

from app.ai.runtime import build_rag_agent_runtime
from app.core.config import Settings


def test_runtime_composes_retriever_ollama_and_graph_from_settings():
    settings = Settings(
        chroma_host="chroma",
        chroma_port=8000,
        chroma_official_collection="official-test",
        rag_embedding_model="BAAI/bge-m3",
        rag_top_k=3,
        ollama_base_url="http://ollama:11434",
        ollama_model="test-model",
        ollama_timeout_seconds=7.5,
    )
    search = object()
    graph = object()

    with (
        patch("app.ai.runtime.OfficialRetrievalAdapter.connect", return_value=search) as connect,
        patch("app.ai.runtime.OllamaClient") as ollama_client,
        patch("app.ai.runtime.build_rag_agent_graph", return_value=graph) as build_graph,
    ):
        runtime = build_rag_agent_runtime(settings)

    search_settings = connect.call_args.args[0]
    assert (search_settings.host, search_settings.port) == ("chroma", 8000)
    assert search_settings.collection == "official-test"
    assert ollama_client.call_args.kwargs == {
        "base_url": "http://ollama:11434",
        "model": "test-model",
        "timeout_seconds": 7.5,
    }
    assert build_graph.call_args.kwargs["search"] is search
    assert build_graph.call_args.kwargs["top_k"] == 3
    assert runtime.search is search
    assert runtime.graph is graph
