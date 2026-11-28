"""Repeatable property-based evaluation for a local LLM response contract."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from app.ai.guardrails import is_korean_internal_note, validate_customer_draft_text
from app.ai.models import DraftAction, DraftRequest, Evidence, EvidenceKind
from app.ai.ollama import OllamaClient
from app.ai.prompting import build_prompt


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    question: str
    expected_action: DraftAction
    official_evidence: list[Evidence]
    voc_references: list[Evidence]


def parse_case(value: dict[str, Any]) -> EvaluationCase:
    def evidence(rows: list[dict[str, str]], kind: EvidenceKind) -> list[Evidence]:
        return [Evidence(row["source_id"], row["title"], row["excerpt"], kind) for row in rows]

    return EvaluationCase(
        case_id=str(value["id"]),
        question=str(value["question"]),
        expected_action=DraftAction(value["expected_action"]),
        official_evidence=evidence(value.get("official_evidence", []), EvidenceKind.OFFICIAL),
        voc_references=evidence(value.get("voc_references", []), EvidenceKind.VOC_REFERENCE),
    )


def score_response(case: EvaluationCase, raw: str) -> tuple[bool, list[str], str | None]:
    """Score stable properties, never an exact Korean sentence match."""
    failures: list[str] = []
    try:
        response = json.loads(raw)
        action = DraftAction(response["action"])
        draft = response.get("draft_text")
        reason = response.get("escalation_reason")
        citations = response.get("cited_source_ids")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return False, ["invalid_json_contract"], None
    if action is not case.expected_action:
        failures.append("unexpected_action")
    ids = {item.source_id for item in case.official_evidence}
    if not isinstance(citations, list) or not all(isinstance(item, str) for item in citations):
        failures.append("invalid_citations")
    elif not set(citations).issubset(ids):
        failures.append("non_official_citation")
    if action is DraftAction.DRAFT_FOR_REVIEW:
        if not isinstance(draft, str) or not draft.strip() or not citations or reason is not None:
            failures.append("invalid_draft_contract")
        elif draft:
            try:
                validate_customer_draft_text(draft)
            except ValueError:
                failures.append("unsafe_draft_text")
    elif draft is not None or citations != [] or not isinstance(reason, str) or not reason.strip():
        failures.append("invalid_escalation_contract")
    elif not is_korean_internal_note(reason):
        failures.append("non_korean_escalation_reason")
    return not failures, failures, action.value


def evaluate_case(case: EvaluationCase, client: OllamaClient) -> dict[str, Any]:
    request = DraftRequest(case.question, case.official_evidence, case.voc_references)
    generation = client.generate_json(build_prompt(request))
    passed, failures, action = score_response(case, generation.text)
    return {
        "case_id": case.case_id,
        "expected_action": case.expected_action.value,
        "actual_action": action,
        "passed": passed,
        "failures": failures,
        "latency_ms": generation.latency_ms,
        "prompt_tokens": generation.prompt_tokens,
        "completion_tokens": generation.completion_tokens,
    }
