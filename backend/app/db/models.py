from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    true,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.ai.models import DraftAction, EvidenceKind, GenerationStatus
from app.db.base import Base


class InquiryStatus(StrEnum):
    """문의 처리 상태. 전환 규칙은 노션 '관리자 문의 상태 변경' 참고."""

    DRAFT_GENERATING = "DRAFT_GENERATING"
    PENDING_REVIEW = "PENDING_REVIEW"
    IN_REVIEW = "IN_REVIEW"
    ANSWERED = "ANSWERED"
    CLOSED = "CLOSED"


class InquiryType(StrEnum):
    QUESTION = "QUESTION"
    SUGGESTION = "SUGGESTION"
    COMPLIMENT = "COMPLIMENT"
    COMPLAINT = "COMPLAINT"


class GenerationPurpose(StrEnum):
    INQUIRY_DRAFT = "INQUIRY_DRAFT"
    CHAT_ANSWER = "CHAT_ANSWER"


class ChatRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ChatDecision(StrEnum):
    ANSWER = "ANSWER"
    HANDOFF = "HANDOFF"


def _enum(enum_cls: type[StrEnum]) -> SAEnum:
    return SAEnum(enum_cls, native_enum=False, length=32)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------- 기준 정보 ----------

class Brand(TimestampMixin, Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class FaqCategory(Base):
    __tablename__ = "faq_categories"
    __table_args__ = (UniqueConstraint("brand_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class Faq(TimestampMixin, Base):
    __tablename__ = "faqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("faq_categories.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    category: Mapped[FaqCategory] = relationship()


class Store(TimestampMixin, Base):
    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("brand_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100), index=True)
    address: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class InquiryCategory(Base):
    """1:1 문의 분류. 최대 3단계 트리."""

    __tablename__ = "inquiry_categories"
    __table_args__ = (UniqueConstraint("brand_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("inquiry_categories.id"), index=True
    )
    depth: Mapped[int] = mapped_column(default=1, server_default="1")
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    parent: Mapped[InquiryCategory | None] = relationship(
        remote_side="InquiryCategory.id"
    )


# ---------- 1:1 문의 ----------

class Inquiry(TimestampMixin, Base):
    __tablename__ = "inquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)

    # 고객이 보낸 분류 이름 경로 원본 및 가장 깊은 일치 분류
    category_path: Mapped[list[str] | None] = mapped_column(JSON)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("inquiry_categories.id"), index=True
    )
    inquiry_type: Mapped[InquiryType] = mapped_column(
        _enum(InquiryType),
        default=InquiryType.QUESTION,
        server_default=InquiryType.QUESTION.value,
    )

    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    store_name: Mapped[str | None] = mapped_column(String(100))

    # 개인정보: LLM 프롬프트·로그로 보내지 않는다.
    customer_name: Mapped[str] = mapped_column(String(50))
    privacy_consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    receipt_token: Mapped[str] = mapped_column(String(64), unique=True)

    status: Mapped[InquiryStatus] = mapped_column(
        _enum(InquiryStatus),
        default=InquiryStatus.DRAFT_GENERATING,
        server_default=InquiryStatus.DRAFT_GENERATING.value,
        index=True,
    )

    summary: Mapped[str | None] = mapped_column(Text)
    category_suggestion: Mapped[list[str] | None] = mapped_column(JSON)
    admin_memo: Mapped[str | None] = mapped_column(Text)
    answer_content: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    category: Mapped[InquiryCategory | None] = relationship()
    draft: Mapped[AnswerDraft | None] = relationship(
        back_populates="inquiry"
    )


class AnswerDraft(TimestampMixin, Base):
    __tablename__ = "answer_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_id: Mapped[int] = mapped_column(
        ForeignKey("inquiries.id", ondelete="CASCADE"), unique=True
    )

    # AI 결과가 오기 전에 관리자가 먼저 초안을 작성할 수 있다.
    action: Mapped[DraftAction | None] = mapped_column(_enum(DraftAction))
    ai_draft_text: Mapped[str | None] = mapped_column(Text)
    edited_text: Mapped[str | None] = mapped_column(Text)
    escalation_reason: Mapped[str | None] = mapped_column(Text)

    inquiry: Mapped[Inquiry] = relationship(back_populates="draft")


# ---------- 챗봇 ----------

class ChatConversation(TimestampMixin, Base):
    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    session_key: Mapped[str] = mapped_column(String(36), index=True)

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="conversation", order_by="ChatMessage.id"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("chat_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ChatRole] = mapped_column(_enum(ChatRole))
    content: Mapped[str] = mapped_column(Text)
    decision: Mapped[ChatDecision | None] = mapped_column(_enum(ChatDecision))
    handoff_reason: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation: Mapped[ChatConversation] = relationship(
        back_populates="messages"
    )


# ---------- AI 실행 로그 ----------

class AiGenerationLog(Base):
    __tablename__ = "ai_generation_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    purpose: Mapped[GenerationPurpose] = mapped_column(
        _enum(GenerationPurpose), index=True
    )
    inquiry_id: Mapped[int | None] = mapped_column(
        ForeignKey("inquiries.id", ondelete="CASCADE"), index=True
    )
    chat_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[GenerationStatus] = mapped_column(_enum(GenerationStatus))
    action: Mapped[DraftAction] = mapped_column(_enum(DraftAction))
    latency_ms: Mapped[int]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    sources: Mapped[list[AiGenerationSource]] = relationship(
        back_populates="generation_log"
    )


class AiGenerationSource(Base):
    __tablename__ = "ai_generation_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    generation_log_id: Mapped[int] = mapped_column(
        ForeignKey("ai_generation_logs.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[str] = mapped_column(String(200))
    document_id: Mapped[str | None] = mapped_column(String(200))
    title: Mapped[str | None] = mapped_column(String(255))
    excerpt: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    kind: Mapped[EvidenceKind] = mapped_column(_enum(EvidenceKind))
    cited: Mapped[bool] = mapped_column(default=False, server_default="false")

    generation_log: Mapped[AiGenerationLog] = relationship(
        back_populates="sources"
    )