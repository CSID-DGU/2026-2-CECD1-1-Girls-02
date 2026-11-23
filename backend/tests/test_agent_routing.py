from app.ai.agent import _needs_rule_handoff


def test_general_question_continues_to_retrieval():
    assert not _needs_rule_handoff({"inquiry_text": "멤버십 혜택이 궁금합니다."})


def test_order_or_individual_franchise_question_routes_to_handoff():
    assert _needs_rule_handoff({"inquiry_text": "주문 상태를 확인해주세요.", "has_individual_order_context": True})
    assert _needs_rule_handoff({"inquiry_text": "우리 동네 창업 상담을 신청하고 싶어요."})
