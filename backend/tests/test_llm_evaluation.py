from app.ai.evaluation import parse_case, score_response


def _case(expected_action: str = "DRAFT_FOR_REVIEW"):
    return parse_case({"id": "case", "question": "질문", "expected_action": expected_action, "official_evidence": [{"source_id": "policy-1", "title": "정책", "excerpt": "공식 근거"}]})


def test_evaluator_accepts_a_grounded_draft_without_matching_exact_wording() -> None:
    passed, failures, action = score_response(_case(), '{"action":"DRAFT_FOR_REVIEW","draft_text":"공식 안내에 따라 이용하실 수 있습니다.","escalation_reason":null,"cited_source_ids":["policy-1"]}')
    assert passed
    assert failures == []
    assert action == "DRAFT_FOR_REVIEW"


def test_evaluator_rejects_unsafe_or_non_official_outputs() -> None:
    passed, failures, _ = score_response(_case(), '{"action":"DRAFT_FOR_REVIEW","draft_text":"[policy-1]을 참고하세요.","escalation_reason":null,"cited_source_ids":["policy-1"]}')
    assert not passed
    assert failures == ["unsafe_draft_text"]


def test_evaluator_rejects_english_escalation_reason() -> None:
    passed, failures, _ = score_response(_case("ESCALATE"), '{"action":"ESCALATE","draft_text":null,"escalation_reason":"Account verification is required.","cited_source_ids":[]}')
    assert not passed
    assert failures == ["non_korean_escalation_reason"]


def test_evaluator_requires_empty_citations_for_escalation() -> None:
    passed, failures, _ = score_response(
        _case("ESCALATE"),
        '{"action":"ESCALATE","draft_text":null,"escalation_reason":"공식 근거가 부족합니다.","cited_source_ids":["policy-1"]}',
    )
    assert not passed
    assert failures == ["invalid_escalation_contract"]
