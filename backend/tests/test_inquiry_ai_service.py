from __future__ import annotations

import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.models import DraftAction, DraftResult, EvidenceKind, GenerationEvent, GenerationStatus
from app.ai.service import InquiryAiCommand, InquiryAiService
from app.core.errors import AppError, ErrorCode
from app.db.base import Base
from app.db.models import AiGenerationLog, AnswerDraft, Inquiry, InquiryStatus


class FakeGraph:
    def __init__(self, result: DraftResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def invoke(self, input: dict[str, object]) -> dict[str, object]:
        self.calls.append(input)
        return {"result": self.result}


def _result(action: DraftAction) -> DraftResult:
    is_draft = action is DraftAction.DRAFT_FOR_REVIEW
    return DraftResult(
        action=action,
        draft_text="검토용 답변 초안" if is_draft else None,
        escalation_reason=None if is_draft else "공식 근거가 부족합니다.",
        cited_source_ids=["faq:2"] if is_draft else [],
        event=GenerationEvent(
            model="test-model",
            prompt_version="v1",
            official_source_ids=["faq:1", "faq:2"],
            voc_reference_ids=["case:1"],
            latency_ms=12,
            status=GenerationStatus.COMPLETED if is_draft else GenerationStatus.RULE_ESCALATED,
        ),
    )


class InquiryAiServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session: Session = sessionmaker(bind=engine, expire_on_commit=False)()
        with self.session.begin():
            inquiry = Inquiry(
                brand_id=1,
                category_id=1,
                title="멤버십 문의",
                content="혜택이 궁금합니다.",
                customer_name="Test Customer",
                customer_contact="010-0000-0000",
                receipt_token="receipt-test-1",
            )
            self.session.add(inquiry)
            self.session.flush()
            self.inquiry_id = inquiry.id

    def tearDown(self) -> None:
        self.session.close()

    def test_saves_draft_status_log_and_sources_without_personal_fields_in_agent_input(self) -> None:
        graph = FakeGraph(_result(DraftAction.DRAFT_FOR_REVIEW))
        result = InquiryAiService(self.session, graph).generate_draft(
            InquiryAiCommand(self.inquiry_id)
        )

        inquiry = self.session.get(Inquiry, self.inquiry_id)
        draft = self.session.scalar(select(AnswerDraft))
        log = self.session.scalar(select(AiGenerationLog))

        self.assertIs(result.action, DraftAction.DRAFT_FOR_REVIEW)
        self.assertIs(inquiry.status, InquiryStatus.AI_DRAFTED)
        self.assertEqual(draft.ai_draft_text, "검토용 답변 초안")
        self.assertIsNone(draft.escalation_reason)
        self.assertEqual(log.model, "test-model")
        self.assertEqual([(item.source_id, item.kind, item.cited) for item in log.sources], [
            ("faq:1", EvidenceKind.OFFICIAL, False),
            ("faq:2", EvidenceKind.OFFICIAL, True),
            ("case:1", EvidenceKind.VOC_REFERENCE, False),
        ])
        self.assertIn("멤버십 문의", graph.calls[0]["inquiry_text"])
        self.assertNotIn("Test Customer", graph.calls[0]["inquiry_text"])
        self.assertNotIn("010-0000-0000", graph.calls[0]["inquiry_text"])

    def test_saves_escalation_reason_and_status(self) -> None:
        result = InquiryAiService(self.session, FakeGraph(_result(DraftAction.ESCALATE))).generate_draft(
            InquiryAiCommand(self.inquiry_id)
        )

        inquiry = self.session.get(Inquiry, self.inquiry_id)
        draft = self.session.scalar(select(AnswerDraft))

        self.assertIs(result.action, DraftAction.ESCALATE)
        self.assertIs(inquiry.status, InquiryStatus.ESCALATED)
        self.assertIsNone(draft.ai_draft_text)
        self.assertEqual(draft.escalation_reason, "공식 근거가 부족합니다.")

    def test_rejects_an_inquiry_that_is_not_received_before_calling_agent(self) -> None:
        inquiry = self.session.get(Inquiry, self.inquiry_id)
        inquiry.status = InquiryStatus.AI_DRAFTED
        self.session.commit()
        graph = FakeGraph(_result(DraftAction.DRAFT_FOR_REVIEW))

        with self.assertRaises(AppError) as raised:
            InquiryAiService(self.session, graph).generate_draft(InquiryAiCommand(self.inquiry_id))

        self.assertIs(raised.exception.error_code, ErrorCode.CONFLICT)
        self.assertEqual(graph.calls, [])


if __name__ == "__main__":
    unittest.main()
