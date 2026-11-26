from __future__ import annotations

import json
from dataclasses import dataclass

from app.ai.guardrails import evaluate_input_guardrail, is_korean_internal_note, validate_customer_draft_text
from app.ai.handoff import requires_franchise_handoff
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
            return self._escalated("AI 응답 생성에 실패하여 담당자 검토가 필요합니다.", official_ids, voc_ids, GenerationStatus.MODEL_ERROR, 0)
        try:
            output = self._validate_model_output(generation.text, set(official_ids))
        except ValueError:
            return self._escalated("AI 응답이 안전 형식 검증을 통과하지 않아 담당자 검토가 필요합니다.", official_ids, voc_ids, GenerationStatus.INVALID_MODEL_OUTPUT, generation.latency_ms)
        return DraftResult(output.action, output.draft_text, output.escalation_reason, output.cited_source_ids, self._event(official_ids, voc_ids, generation.latency_ms, GenerationStatus.COMPLETED))

    def _required_escalation_reason(self, request: DraftRequest) -> str | None:
        guardrail = evaluate_input_guardrail(request.inquiry_text)
        if guardrail.should_handoff:
            return guardrail.reason
        if request.has_individual_order_context:
            return "개별 주문 또는 계정 확인이 필요합니다."
        if requires_franchise_handoff(request.inquiry_text):
            return "개별 창업 상담은 담당자 검토가 필요합니다."
        if request.is_sensitive:
            return "민감한 문의는 담당자 검토가 필요합니다."
        if request.is_safety_related or any(term in request.inquiry_text for term in _RISK_TERMS):
            return "안전 또는 긴급 위험 관련 문의는 담당자가 즉시 처리해야 합니다."
        if request.is_urgent:
            return "긴급 문의는 담당자 확인이 필요합니다."
        if request.retrieval_failed:
            return "공식 지식 검색을 사용할 수 없어 담당자 검토가 필요합니다."
        if not request.official_evidence:
            return "공식 근거가 부족하여 담당자 검토가 필요합니다."
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
            validate_customer_draft_text(draft_text)
        elif (
            draft_text is not None
            or not isinstance(reason, str)
            or not reason.strip()
            or not is_korean_internal_note(reason)
        ):
            raise ValueError("invalid escalation")
        return _ValidatedOutput(action, draft_text, reason, citations)

    def _event(self, official: list[str], voc: list[str], latency_ms: int, status: GenerationStatus) -> GenerationEvent:
        return GenerationEvent(self.client.model, PROMPT_VERSION, official, voc, latency_ms, status)

    def _escalated(self, reason: str, official: list[str], voc: list[str], status: GenerationStatus, latency_ms: int) -> DraftResult:
        return DraftResult(DraftAction.ESCALATE, None, reason, [], self._event(official, voc, latency_ms, status))
