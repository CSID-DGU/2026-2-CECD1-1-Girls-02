"""Deterministic handoff rules that must run before local-model generation."""
from __future__ import annotations


_FRANCHISE_TERMS = ("창업", "가맹", "가맹점", "점주", "매장 개설", "출점")
_INDIVIDUAL_FRANCHISE_TERMS = (
    "상담 신청",
    "상담 접수",
    "상담받",
    "상담 받",
    "입지",
    "상권",
    "출점 가능",
    "가맹 계약",
    "계약 조건",
    "우리 동네",
    "제 지역",
    "내 지역",
)
_INDIVIDUAL_ORDER_TERMS = (
    "주문번호",
    "주문 내역",
    "주문상태",
    "주문 상태",
    "내 주문",
    "결제 내역",
    "배달 상태",
    "배송 상태",
)


def requires_franchise_handoff(inquiry_text: str) -> bool:
    """Escalate only individualized franchise requests, not general knowledge questions."""
    normalized = inquiry_text.casefold()
    is_franchise_question = any(term in normalized for term in _FRANCHISE_TERMS)
    needs_individual_judgment = any(term in normalized for term in _INDIVIDUAL_FRANCHISE_TERMS)
    return is_franchise_question and needs_individual_judgment


def requires_individual_order_handoff(inquiry_text: str) -> bool:
    """Keep order-specific requests out of the automatic-answer path."""
    normalized = inquiry_text.casefold()
    return any(term in normalized for term in _INDIVIDUAL_ORDER_TERMS)
