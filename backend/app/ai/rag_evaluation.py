"""Evaluation of real official-knowledge retrieval and routing decisions."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from app.ai.answerability import assess_answerability
from app.ai.context import RetrievedChunk, build_official_context
from app.ai.guardrails import evaluate_input_guardrail


class ExpectedDecision(StrEnum):
    GENERATE = "GENERATE"
    HANDOFF = "HANDOFF"


class OfficialSearch(Protocol):
    def search_official(self, query: str, *, top_k: int) -> Iterable[RetrievedChunk]: ...


@dataclass(frozen=True)
class RetrievalEvaluationCase:
    case_id: str
    query: str
    expected_categories: tuple[str, ...]
    expected_source_ids: tuple[str, ...]
    expected_decision: ExpectedDecision


def parse_case(value: dict[str, Any]) -> RetrievalEvaluationCase:
    return RetrievalEvaluationCase(
        case_id=str(value["id"]),
        query=str(value["query"]),
        expected_categories=tuple(str(item).upper() for item in value.get("expected_categories", [])),
        expected_source_ids=tuple(str(item) for item in value.get("expected_source_ids", [])),
        expected_decision=ExpectedDecision(value["expected_decision"]),
    )


def evaluate_case(case: RetrievalEvaluationCase, search: OfficialSearch, *, top_k: int) -> dict[str, Any]:
    """Evaluate one case without letting an LLM hide a retrieval failure."""
    input_guardrail = evaluate_input_guardrail(case.query)
    if input_guardrail.should_handoff:
        actual = ExpectedDecision.HANDOFF
        hits: tuple[RetrievedChunk, ...] = ()
        selected: tuple[RetrievedChunk, ...] = ()
    else:
        hits = tuple(search.search_official(case.query, top_k=top_k))
        assessment = assess_answerability(case.query, hits)
        context = build_official_context(assessment.eligible_hits, max_chunks=top_k)
        selected = tuple(
            hit for hit in assessment.eligible_hits if hit.chunk_id in set(context.selected_chunk_ids)
        )
        actual = ExpectedDecision.GENERATE if context.official_evidence else ExpectedDecision.HANDOFF

    retrieved_source_ids = tuple(
        str(hit.metadata.get("source_id")) for hit in hits if isinstance(hit.metadata.get("source_id"), str)
    )
    selected_categories = tuple(
        str(hit.metadata.get("category", "")).upper() for hit in selected
    )
    expected_sources = set(case.expected_source_ids)
    recall_hit = None if not expected_sources else bool(expected_sources.intersection(retrieved_source_ids))
    allowed_categories = set(case.expected_categories) | {"GENERAL"}
    category_match = None if not case.expected_categories else bool(selected_categories) and all(
        category in allowed_categories for category in selected_categories
    )
    return {
        "case_id": case.case_id,
        "expected_decision": case.expected_decision.value,
        "actual_decision": actual.value,
        "decision_match": actual is case.expected_decision,
        "expected_source_ids": list(case.expected_source_ids),
        "retrieved_source_ids": list(retrieved_source_ids),
        "recall_at_k": recall_hit,
        "expected_categories": list(case.expected_categories),
        "selected_categories": list(selected_categories),
        "category_match": category_match,
        "input_guardrail_reason": input_guardrail.reason_code,
    }


def summarize(results: Iterable[dict[str, Any]]) -> dict[str, float | int]:
    rows = list(results)
    answerable = [row for row in rows if row["expected_decision"] == ExpectedDecision.GENERATE.value]
    handoff = [row for row in rows if row["expected_decision"] == ExpectedDecision.HANDOFF.value]
    recall_rows = [row for row in answerable if row["recall_at_k"] is not None]
    category_rows = [row for row in answerable if row["category_match"] is not None]
    return {
        "total": len(rows),
        "decision_accuracy": sum(bool(row["decision_match"]) for row in rows) / len(rows) if rows else 0.0,
        "recall_at_k": sum(bool(row["recall_at_k"]) for row in recall_rows) / len(recall_rows) if recall_rows else 0.0,
        "category_match_rate": sum(bool(row["category_match"]) for row in category_rows) / len(category_rows) if category_rows else 0.0,
        "unsafe_generate_rate": sum(row["actual_decision"] == ExpectedDecision.GENERATE.value for row in handoff) / len(handoff) if handoff else 0.0,
        "over_handoff_rate": sum(row["actual_decision"] == ExpectedDecision.HANDOFF.value for row in answerable) / len(answerable) if answerable else 0.0,
    }
