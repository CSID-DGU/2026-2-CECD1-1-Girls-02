"""Deterministic evidence-sufficiency checks before customer draft generation.

This layer does not try to improve retrieval ranking.  It answers a narrower
question: may the retrieved official evidence be used for this inquiry at all?
Keeping the check independent from dense/RRF/reranker scores avoids treating
incomparable retrieval scores as a universal confidence value.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from collections.abc import Iterable
import unicodedata

from app.ai.context import RetrievedChunk


class AnswerabilityDecision(StrEnum):
    GENERATE = "GENERATE"
    HANDOFF = "HANDOFF"


@dataclass(frozen=True)
class AnswerabilityAssessment:
    """Explain which retrieved chunks may become LLM context."""

    decision: AnswerabilityDecision
    inferred_categories: tuple[str, ...]
    eligible_hits: tuple[RetrievedChunk, ...]
    rejected_chunk_ids: tuple[str, ...]
    reason: str | None = None


# This is deliberately small and explainable.  Unknown wording is not forced
# into a category; retrieval can still serve an exact general-policy query.
_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("MEMBERSHIP", ("멤버십", "회원가입", "가입", "회원 등급", "스탬프", "VIP", "GOLD", "SILVER")),
    ("DELIVERY", ("배달", "배송")),
    ("FRANCHISE", ("창업", "가맹")),
    ("COUPON", ("쿠폰", "할인", "프로모션", "제휴")),
    ("PRODUCT", ("메뉴", "피자", "토핑", "사이드", "핫소스", "치즈", "알레르기", "칼로리")),
    ("ORDER", ("주문", "결제", "취소", "변경")),
)


def infer_query_categories(inquiry_text: str) -> tuple[str, ...]:
    """Infer only explicit business-domain hints from a customer inquiry."""
    # Browser, mobile keyboard, and copy/paste inputs can carry decomposed
    # Hangul (NFD) or zero-width characters.  Normalize before keyword
    # matching so an equivalent customer word never silently bypasses a gate.
    normalized = unicodedata.normalize("NFC", inquiry_text).replace("\u200b", "").casefold()
    # The first matching domain is the primary intent.  A delivery-order
    # question should search DELIVERY, not mix every ORDER document into its
    # answer context merely because the word "order" is present.
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(unicodedata.normalize("NFC", keyword).casefold() in normalized for keyword in keywords):
            return (category,)
    return ()


def assess_answerability(
    inquiry_text: str, hits: Iterable[RetrievedChunk]
) -> AnswerabilityAssessment:
    """Remove category-mismatched hits and block generation when none remain.

    A category hint is a safety constraint, not a retrieval-rank adjustment.
    `GENERAL` stays eligible as the agreed fallback category for official
    documents that legitimately apply across business domains.
    """
    candidates = tuple(hits)
    inferred = infer_query_categories(inquiry_text)
    if not inferred:
        return AnswerabilityAssessment(
            AnswerabilityDecision.GENERATE,
            inferred,
            candidates,
            (),
        )

    allowed = set(inferred) | {"GENERAL"}
    eligible: list[RetrievedChunk] = []
    rejected: list[str] = []
    for hit in candidates:
        category = hit.metadata.get("category")
        if isinstance(category, str) and category.strip().upper() in allowed:
            eligible.append(hit)
        else:
            rejected.append(hit.chunk_id)

    if eligible:
        return AnswerabilityAssessment(
            AnswerabilityDecision.GENERATE,
            inferred,
            tuple(eligible),
            tuple(rejected),
        )
    return AnswerabilityAssessment(
        AnswerabilityDecision.HANDOFF,
        inferred,
        (),
        tuple(rejected),
        "질문 카테고리와 일치하는 공식 근거가 부족합니다.",
    )
