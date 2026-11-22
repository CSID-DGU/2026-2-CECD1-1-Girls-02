from __future__ import annotations

import json
from dataclasses import dataclass

from app.ai.models import DraftAction, DraftRequest, DraftResult, GenerationEvent, GenerationStatus
from app.ai.ollama import OllamaClient, OllamaError
from app.ai.prompting import PROMPT_VERSION, build_prompt

_RISK_TERMS = ("응급", "긴급", "위험", "안전", "자해", "폭력", "사고")


@dataclass(frozen=True)
class _ValidatedOutput:
    action: DraftAction
    draft_text: str | None
    escalation_reason: str | None
    cited_source_ids: list[str]


class DraftOrchestrator:
    def __init__(self, client: OllamaClient) -> None:
        self.client = client

    def create_draft(self, request: DraftRequest) -> DraftResult:
        official_ids = [item.source_id for item in request.official_evidence]
        voc_ids = [item.source_id for item in request.voc_references]
        rule_reason = self._required_escalation_reason(request)
        if rule_reason:
            return self._escalated(rule_reason, official_ids, voc_ids, GenerationStatus.RULE_ESCALATED, 0)
        try:
            generation = self.client.generate_json(build_prompt(request))
        except OllamaError:
            return self._escalated("Local model generation failed; agent review is required.", official_ids, voc_ids, GenerationStatus.MODEL_ERROR, 0)
        try:
            output = self._validate_model_output(generation.text, set(official_ids))
        except ValueError:
            return self._escalated("Model output did not satisfy the review safety contract.", official_ids, voc_ids, GenerationStatus.INVALID_MODEL_OUTPUT, generation.latency_ms)
        return DraftResult(output.action, output.draft_text, output.escalation_reason, output.cited_source_ids, self._event(official_ids, voc_ids, generation.latency_ms, GenerationStatus.COMPLETED))

    def _required_escalation_reason(self, request: DraftRequest) -> str | None:
        if request.has_individual_order_context:
            return "Individual order/account verification is required."
        if request.is_sensitive:
            return "Sensitive inquiry requires specialist review."
        if request.is_safety_related or any(term in request.inquiry_text for term in _RISK_TERMS):
            return "Safety or urgent-risk inquiry requires immediate human handling."
        if request.is_urgent:
            return "Urgent inquiry requires human handling."
        if not request.official_evidence:
            return "No authoritative official evidence is available."
        return None

    def _validate_model_output(self, raw: str, official_ids: set[str]) -> _ValidatedOutput:
        try:
            value = json.loads(raw)
            action = DraftAction(value["action"])
            draft_text, reason, citations = value.get("draft_text"), value.get("escalation_reason"), value.get("cited_source_ids")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid JSON contract") from exc
        if not isinstance(citations, list) or not all(isinstance(item, str) for item in citations) or not set(citations).issubset(official_ids):
            raise ValueError("invalid or non-official citations")
        if action is DraftAction.DRAFT_FOR_REVIEW:
            if not isinstance(draft_text, str) or not draft_text.strip() or not citations or reason is not None:
                raise ValueError("unsupported draft")
        elif draft_text is not None or not isinstance(reason, str) or not reason.strip():
            raise ValueError("invalid escalation")
        return _ValidatedOutput(action, draft_text, reason, citations)

    def _event(self, official: list[str], voc: list[str], latency_ms: int, status: GenerationStatus) -> GenerationEvent:
        return GenerationEvent(self.client.model, PROMPT_VERSION, official, voc, latency_ms, status)

    def _escalated(self, reason: str, official: list[str], voc: list[str], status: GenerationStatus, latency_ms: int) -> DraftResult:
        return DraftResult(DraftAction.ESCALATE, None, reason, [], self._event(official, voc, latency_ms, status))
