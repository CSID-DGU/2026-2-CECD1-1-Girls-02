import json
from pathlib import Path

from app.ai.context import RetrievedChunk
from app.ai.rag_evaluation import ExpectedDecision, evaluate_case, parse_case, summarize


class FakeSearch:
    def __init__(self, hits: list[RetrievedChunk]) -> None:
        self.hits = hits

    def search_official(self, query: str, *, top_k: int) -> list[RetrievedChunk]:
        return self.hits


def _hit(source_id: str, category: str) -> RetrievedChunk:
    return RetrievedChunk(
        source_id,
        "공식 안내",
        0.9,
        {
            "source_id": source_id,
            "title": "공식 문서",
            "category": category,
            "knowledge_scope": "official",
            "is_active": True,
            "review_status": "APPROVED",
            "allowed_use": "DRAFT_ONLY",
        },
    )


def test_scores_recall_category_and_generate_route_for_matching_evidence():
    case = parse_case({"id": "r1", "query": "멤버십 혜택", "expected_categories": ["MEMBERSHIP"], "expected_source_ids": ["faq:membership"], "expected_decision": "GENERATE"})

    result = evaluate_case(case, FakeSearch([_hit("faq:membership", "MEMBERSHIP")]), top_k=3)

    assert result["actual_decision"] == ExpectedDecision.GENERATE.value
    assert result["recall_at_k"] is True
    assert result["category_match"] is True


def test_scores_handoff_without_running_retrieval_for_personal_order():
    case = parse_case({"id": "r2", "query": "제 주문 상태를 확인해 주세요.", "expected_categories": [], "expected_source_ids": [], "expected_decision": "HANDOFF"})

    result = evaluate_case(case, FakeSearch([_hit("faq:order", "ORDER")]), top_k=3)

    assert result["actual_decision"] == ExpectedDecision.HANDOFF.value
    assert result["retrieved_source_ids"] == []
    assert result["input_guardrail_reason"] in {"ACCOUNT_VERIFICATION", "INDIVIDUAL_ORDER"}


def test_scores_handoff_without_retrieval_for_individual_location():
    case = parse_case({"id": "r3", "query": "우리 동네 매장의 배달료를 확인해 주세요.", "expected_categories": [], "expected_source_ids": [], "expected_decision": "HANDOFF"})

    result = evaluate_case(case, FakeSearch([_hit("faq:delivery", "DELIVERY")]), top_k=3)

    assert result["actual_decision"] == ExpectedDecision.HANDOFF.value
    assert result["input_guardrail_reason"] in {"ACCOUNT_VERIFICATION", "INDIVIDUAL_ORDER"}


def test_summary_distinguishes_unsafe_generation_and_over_handoff():
    summary = summarize([
        {"expected_decision": "GENERATE", "actual_decision": "GENERATE", "decision_match": True, "recall_at_k": True, "category_match": True},
        {"expected_decision": "GENERATE", "actual_decision": "HANDOFF", "decision_match": False, "recall_at_k": False, "category_match": False},
        {"expected_decision": "HANDOFF", "actual_decision": "GENERATE", "decision_match": False, "recall_at_k": None, "category_match": None},
        {"expected_decision": "HANDOFF", "actual_decision": "HANDOFF", "decision_match": True, "recall_at_k": None, "category_match": None},
    ])

    assert summary["recall_at_k"] == 0.5
    assert summary["category_match_rate"] == 0.5
    assert summary["unsafe_generate_rate"] == 0.5
    assert summary["over_handoff_rate"] == 0.5


def test_challenge_fixture_has_unique_and_parseable_cases():
    path = Path(__file__).parent / "fixtures" / "rag_challenge_cases.json"
    cases = [parse_case(value) for value in json.loads(path.read_text(encoding="utf-8"))]

    assert len(cases) == 16
    assert len({case.case_id for case in cases}) == len(cases)
    assert {case.expected_decision for case in cases} == {
        ExpectedDecision.GENERATE,
        ExpectedDecision.HANDOFF,
    }
