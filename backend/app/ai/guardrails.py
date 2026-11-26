"""Deterministic safety gates around customer-facing AI generation.

The local model can recommend an action, but it never gets to override these
rules.  Keeping these decisions in code makes the reason reproducible and
prevents a prompt regression from exposing an individual customer's data.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from app.ai.handoff import requires_franchise_handoff, requires_individual_order_handoff


_ACCOUNT_TARGETS = ("계정", "포인트", "적립", "쿠폰", "결제", "주문", "배송", "배달")
_PERSONAL_REFERENCE = re.compile(
    r"(?:내|제|저의|고객님의)\s*(?:계정|포인트|적립|쿠폰|결제|주문|배송|배달)|"
    r"(?:내가|제가|저는).{0,12}(?:확인|조회|사라|누락|복구|변동)",
)
_ACCOUNT_STATE = re.compile(r"(?:확인|조회|내역|사라|소멸|안\s*보|누락|복구|변동|적용.*안|반영.*안)")
_POLICY_INFORMATION = re.compile(r"(?:정책|기준|조건|방법|안내|유효\s*기간|가능\s*여부)")
_PROMPT_INJECTION = re.compile(
    r"(?:이전\s*지시|규칙|시스템\s*프롬프트).{0,20}(?:무시|바꿔|따르)|"
    r"(?:무조건|반드시).{0,30}(?:DRAFT_FOR_REVIEW|ESCALATE)|"
    r"(?:DRAFT_FOR_REVIEW|ESCALATE).{0,20}(?:로\s*답|를\s*출력)",
    re.IGNORECASE,
)
_URL_OR_MARKDOWN = re.compile(r"https?://|\]\(", re.IGNORECASE)
_SOURCE_IDENTIFIER = re.compile(r"(?:source[_ ]?id|(?:policy|faq|voc)-[a-z0-9_-]+)", re.IGNORECASE)
_DIRECT_IDENTIFIER_REQUEST = re.compile(
    r"(?:주문\s*번호|연락처|전화\s*번호|계정\s*정보).{0,16}(?:알려|입력|전달|보내|기재)",
)


@dataclass(frozen=True)
class InputGuardrailDecision:
    should_handoff: bool
    reason_code: str | None = None
    reason: str | None = None


def requires_account_verification_handoff(inquiry_text: str) -> bool:
    """Block personal state checks without blocking general policy questions."""
    normalized = inquiry_text.casefold()
    has_account_target = any(term in normalized for term in _ACCOUNT_TARGETS)
    if has_account_target and _POLICY_INFORMATION.search(normalized):
        return False
    return has_account_target and bool(
        _PERSONAL_REFERENCE.search(normalized) or _ACCOUNT_STATE.search(normalized)
    )


def evaluate_input_guardrail(inquiry_text: str) -> InputGuardrailDecision:
    """Return a deterministic pre-retrieval decision for one customer inquiry."""
    if _PROMPT_INJECTION.search(inquiry_text):
        return InputGuardrailDecision(True, "PROMPT_INJECTION", "요청 형식 검증이 필요해 담당자 검토로 전환합니다.")
    if requires_account_verification_handoff(inquiry_text):
        return InputGuardrailDecision(True, "ACCOUNT_VERIFICATION", "개인 계정의 포인트·쿠폰·결제 내역 확인이 필요합니다.")
    if requires_individual_order_handoff(inquiry_text):
        return InputGuardrailDecision(True, "INDIVIDUAL_ORDER", "개별 주문 또는 배송 상태 확인이 필요합니다.")
    if requires_franchise_handoff(inquiry_text):
        return InputGuardrailDecision(True, "INDIVIDUAL_FRANCHISE", "개별 창업 상담은 담당자 검토가 필요합니다.")
    return InputGuardrailDecision(False)


def validate_customer_draft_text(text: str) -> None:
    """Reject output that leaks model-facing identifiers or asks for identifiers."""
    if _URL_OR_MARKDOWN.search(text) or _SOURCE_IDENTIFIER.search(text):
        raise ValueError("customer draft contains a link or internal source identifier")
    if _DIRECT_IDENTIFIER_REQUEST.search(text):
        raise ValueError("customer draft requests a direct identifier")


def is_korean_internal_note(text: str) -> bool:
    """Allow common acronyms but reject an English-only escalation reason."""
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return False
    hangul = sum("가" <= character <= "힣" for character in letters)
    return hangul / len(letters) >= 0.5
