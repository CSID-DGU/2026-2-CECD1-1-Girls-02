import unicodedata

from app.ai.answerability import AnswerabilityDecision, assess_answerability, infer_query_categories
from app.ai.context import RetrievedChunk


def _hit(chunk_id: str, category: str) -> RetrievedChunk:
    return RetrievedChunk(chunk_id, "공식 안내", 0.9, {"category": category})


def test_infers_only_explicit_categories():
    assert infer_query_categories("멤버십 쿠폰 혜택이 궁금해요") == ("MEMBERSHIP", "COUPON")
    assert infer_query_categories("영업시간을 알려주세요") == ()


def test_infers_category_from_decomposed_hangul_input():
    inquiry = unicodedata.normalize("NFD", "멤버십 혜택이 궁금해요")

    assert infer_query_categories(inquiry) == ("MEMBERSHIP",)


def test_keeps_matching_and_general_hits_but_excludes_unrelated_category():
    result = assess_answerability(
        "멤버십 혜택이 궁금해요",
        [_hit("coupon", "COUPON"), _hit("membership", "MEMBERSHIP"), _hit("general", "GENERAL")],
    )

    assert result.decision is AnswerabilityDecision.GENERATE
    assert [hit.chunk_id for hit in result.eligible_hits] == ["membership", "general"]
    assert result.rejected_chunk_ids == ("coupon",)


def test_handoffs_when_explicit_category_has_no_matching_official_evidence():
    result = assess_answerability("멤버십 혜택이 궁금해요", [_hit("product", "PRODUCT")])

    assert result.decision is AnswerabilityDecision.HANDOFF
    assert result.eligible_hits == ()
    assert "일치하는 공식 근거" in (result.reason or "")
