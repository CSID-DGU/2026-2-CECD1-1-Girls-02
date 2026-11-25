from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.ai.models import DraftAction, DraftResult, GenerationEvent, GenerationStatus
from app.api.ai_drafts import get_inquiry_ai_service
from app.main import app


class FakeInquiryAiService:
    def __init__(self, result: DraftResult) -> None:
        self.result = result
        self.inquiry_id: int | None = None

    def generate_draft(self, command):
        self.inquiry_id = command.inquiry_id
        return self.result


def _result(action: DraftAction) -> DraftResult:
    is_draft = action is DraftAction.DRAFT_FOR_REVIEW
    return DraftResult(
        action=action,
        draft_text="검토용 초안" if is_draft else None,
        escalation_reason=None if is_draft else "상담원 확인이 필요합니다.",
        cited_source_ids=["faq:1"] if is_draft else [],
        event=GenerationEvent(
            model="test-model",
            prompt_version="v1",
            official_source_ids=["faq:1"],
            voc_reference_ids=[],
            latency_ms=12,
            status=GenerationStatus.COMPLETED if is_draft else GenerationStatus.RULE_ESCALATED,
        ),
    )


class InquiryDraftApiTests(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_returns_reviewable_draft_response(self) -> None:
        service = FakeInquiryAiService(_result(DraftAction.DRAFT_FOR_REVIEW))
        app.dependency_overrides[get_inquiry_ai_service] = lambda: service

        response = TestClient(app).post("/inquiries/42/ai-draft")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], "AI_DRAFT_CREATED")
        self.assertEqual(response.json()["data"]["cited_source_ids"], ["faq:1"])
        self.assertEqual(service.inquiry_id, 42)

    def test_returns_handoff_response_without_draft_text(self) -> None:
        app.dependency_overrides[get_inquiry_ai_service] = lambda: FakeInquiryAiService(
            _result(DraftAction.ESCALATE)
        )

        response = TestClient(app).post("/inquiries/42/ai-draft")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], "AI_HANDOFF_REQUIRED")
        self.assertIsNone(response.json()["data"]["draft_text"])


if __name__ == "__main__":
    unittest.main()
