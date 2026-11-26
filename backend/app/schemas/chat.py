from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_serializer

from app.core.public_id import CONVERSATION, MESSAGE, format_public_id
from app.db.models import AiGenerationSource, ChatMessage, ChatRole
from app.schemas.common import CamelModel
from app.services.chat_service import INQUIRY_URL, ChatReply, HistoryPage


# ---------- 질문 ----------

class ChatMessageRequest(CamelModel):
    brand_id: str = Field(description="가상 브랜드 ID (예: brand_a)")
    conversation_id: str | None = Field(default=None, description="기존 대화 ID. null이면 새 대화 시작")
    message: str = Field(max_length=1000, description="고객 질문")

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("질문을 입력해 주세요.")
        return value


class AnswerSource(CamelModel):
    document_id: str
    title: str
    excerpt: str


class ChatReplyData(CamelModel):
    conversation_id: str
    mode: str  # ANSWERED | HANDOFF
    answer: str
    sources: list[AnswerSource]
    handoff_reason: str | None
    inquiry_url: str | None
    request_id: str

    @classmethod
    def from_reply(cls, reply: ChatReply) -> "ChatReplyData":
        return cls(
            conversation_id=format_public_id(CONVERSATION, reply.conversation.id),
            mode="ANSWERED" if reply.answered else "HANDOFF",
            answer=reply.answer,
            sources=[AnswerSource(document_id=s.document_id, title=s.title, excerpt=s.excerpt) for s in reply.sources],
            handoff_reason=reply.handoff_reason,
            inquiry_url=None if reply.answered else INQUIRY_URL,
            request_id=reply.request_id,
        )


# ---------- 대화 이력 ----------

class HistorySource(CamelModel):
    document_title: str | None
    chunk_id: str


class HistoryMessage(CamelModel):
    message_id: str
    role: ChatRole
    content: str
    decision: str | None = None
    sources: list[HistorySource] | None = None
    created_at: datetime

    @model_serializer(mode="wrap")
    def _omit_assistant_fields_for_user(self, handler: Any) -> dict[str, Any]:
        data = handler(self)
        if self.role is ChatRole.USER:  # 명세 예시처럼 고객 메시지에는 decision·sources를 넣지 않는다.
            data.pop("decision", None)
            data.pop("sources", None)
        return data

    @classmethod
    def from_model(cls, message: ChatMessage, sources: list[AiGenerationSource]) -> "HistoryMessage":
        is_assistant = message.role is ChatRole.ASSISTANT
        return cls(
            message_id=format_public_id(MESSAGE, message.id),
            role=message.role,
            content=message.content,
            decision=message.decision.value if is_assistant and message.decision else None,
            sources=[HistorySource(document_title=s.title, chunk_id=s.source_id) for s in sources] if is_assistant else None,
            created_at=message.created_at,
        )


class ChatHistoryData(CamelModel):
    conversation_id: str
    status: str
    messages: list[HistoryMessage]
    next_cursor: str | None

    @classmethod
    def from_page(cls, page: HistoryPage) -> "ChatHistoryData":
        return cls(
            conversation_id=format_public_id(CONVERSATION, page.conversation.id),
            status="ACTIVE",
            messages=[HistoryMessage.from_model(m, page.sources_by_message.get(m.id, [])) for m in page.messages],
            next_cursor=format_public_id(MESSAGE, page.next_cursor) if page.next_cursor else None,
        )
