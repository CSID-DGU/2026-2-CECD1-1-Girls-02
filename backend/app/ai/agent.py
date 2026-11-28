"""LangGraph orchestration for the safe RAG answer-draft agent."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypedDict

from app.ai.context import ContextBuildResult, RetrievedChunk, build_official_context
from app.ai.answerability import assess_answerability
from app.ai.guardrails import evaluate_input_guardrail
from app.ai.handoff import requires_franchise_handoff
from app.ai.models import DraftRequest, DraftResult
from app.ai.orchestrator import DraftOrchestrator
from app.ai.retrieval_adapter import OfficialRetrievalUnavailable


class OfficialKnowledgeSearch(Protocol):
    """Adapter implemented by the retrieval owner; only official hits are requested."""

    def search_official(self, query: str, *, top_k: int) -> Iterable[RetrievedChunk]: ...


class AgentState(TypedDict, total=False):
    inquiry_text: str
    has_individual_order_context: bool
    is_sensitive: bool
    is_safety_related: bool
    is_urgent: bool
    retrieval_failed: bool
    answerability_reason: str | None
    context: ContextBuildResult
    result: DraftResult


def _needs_rule_handoff(state: AgentState) -> bool:
    return bool(
        state.get("has_individual_order_context")
        or state.get("is_sensitive")
        or state.get("is_safety_related")
        or state.get("is_urgent")
        or requires_franchise_handoff(state["inquiry_text"])
    )


def _request_from_state(state: AgentState, context: ContextBuildResult | None = None) -> DraftRequest:
    return DraftRequest(
        inquiry_text=state["inquiry_text"],
        official_evidence=context.official_evidence if context else [],
        has_individual_order_context=state.get("has_individual_order_context", False),
        is_sensitive=state.get("is_sensitive", False),
        is_safety_related=state.get("is_safety_related", False),
        is_urgent=state.get("is_urgent", False),
        retrieval_failed=state.get("retrieval_failed", False),
    )


def build_rag_agent_graph(
    *, search: OfficialKnowledgeSearch, orchestrator: DraftOrchestrator, top_k: int = 5
):
    """Build a compiled LangGraph agent without letting the LLM choose safety routes.

    ``langgraph`` is intentionally imported here, so the normal FastAPI test
    suite can run without agent extras installed.
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as error:  # pragma: no cover - dependency boundary
        raise RuntimeError("Install the agent extras to use the LangGraph orchestrator") from error

    def classify(_: AgentState) -> dict[str, object]:
        return {}

    def route_after_classify(state: AgentState) -> str:
        guardrail = evaluate_input_guardrail(state["inquiry_text"])
        return "handoff" if guardrail.should_handoff or _needs_rule_handoff(state) else "retrieve"

    def retrieve(state: AgentState) -> dict[str, object]:
        try:
            hits = search.search_official(state["inquiry_text"], top_k=top_k)
        except OfficialRetrievalUnavailable:
            # A retrieval outage must never fall through to a model-generated answer.
            return {"context": build_official_context([]), "retrieval_failed": True}
        assessment = assess_answerability(state["inquiry_text"], hits)
        context = build_official_context(assessment.eligible_hits, max_chunks=top_k)
        return {
            "context": context,
            "answerability_reason": assessment.reason,
        }

    def route_after_retrieve(state: AgentState) -> str:
        context = state["context"]
        return "generate" if context.official_evidence else "handoff"

    def generate(state: AgentState) -> dict[str, DraftResult]:
        return {"result": orchestrator.create_draft(_request_from_state(state, state["context"]))}

    def handoff(state: AgentState) -> dict[str, DraftResult]:
        return {"result": orchestrator.create_draft(_request_from_state(state))}

    graph = StateGraph(AgentState)
    graph.add_node("classify", classify)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("handoff", handoff)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route_after_classify, {"retrieve": "retrieve", "handoff": "handoff"})
    graph.add_conditional_edges("retrieve", route_after_retrieve, {"generate": "generate", "handoff": "handoff"})
    graph.add_edge("generate", END)
    graph.add_edge("handoff", END)
    return graph.compile()
