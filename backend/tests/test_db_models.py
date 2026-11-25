from app.db import models
from app.db.base import Base

EXPECTED_TABLES = {
    "brands",
    "faq_categories",
    "faqs",
    "stores",
    "inquiry_categories",
    "inquiries",
    "answer_drafts",
    "chat_conversations",
    "chat_messages",
    "ai_generation_logs",
    "ai_generation_sources",
}


def test_all_tables_are_registered() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables)


def test_inquiry_starts_as_received() -> None:
    column = models.Inquiry.__table__.c.status
    assert column.default.arg == models.InquiryStatus.RECEIVED


def test_receipt_token_is_unique() -> None:
    assert models.Inquiry.__table__.c.receipt_token.unique