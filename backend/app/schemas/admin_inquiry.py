from datetime import datetime

from pydantic import Field, field_validator

from app.core.public_id import INQUIRY, format_public_id
from app.db.models import (
    AiGenerationSource,
    AnswerDraft,
    Inquiry,
    InquiryStatus,
)
from app.schemas.common import CamelModel


def _not_blank(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("비어 있을 수 없습니다.")

    return value


# ---------- 목록 ----------

class AdminInquirySummary(CamelModel):
    inquiry_id: str
    title: str
    category_path: list[str]
    status: InquiryStatus
    created_at: datetime

    @classmethod
    def from_model(
        cls, inquiry: Inquiry
    ) -> "AdminInquirySummary":
        return cls(
            inquiry_id=format_public_id(INQUIRY, inquiry.id),
            title=inquiry.title,
            category_path=inquiry.category_path or [],
            status=inquiry.status,
            created_at=inquiry.created_at,
        )


# ---------- 상세 ----------

class SourceItem(CamelModel):
    document_id: str
    title: str | None
    excerpt: str | None

    @classmethod
    def from_model(
        cls, source: AiGenerationSource
    ) -> "SourceItem":
        return cls(
            document_id=source.document_id or source.source_id,
            title=source.title,
            excerpt=source.excerpt,
        )


class DraftData(CamelModel):
    answer_text: str | None
    sources: list[SourceItem]


class AdminInquiryDetail(CamelModel):
    inquiry_id: str
    title: str
    content: str
    customer_name: str
    store_name: str | None
    category_path: list[str]
    summary: str | None
    category_suggestion: list[str] | None
    status: InquiryStatus
    draft: DraftData
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(
        cls,
        inquiry: Inquiry,
        *,
        answer_text: str | None,
        sources: list[AiGenerationSource],
    ) -> "AdminInquiryDetail":
        return cls(
            inquiry_id=format_public_id(INQUIRY, inquiry.id),
            title=inquiry.title,
            content=inquiry.content,
            customer_name=inquiry.customer_name,
            store_name=inquiry.store_name,
            category_path=inquiry.category_path or [],
            summary=inquiry.summary,
            category_suggestion=inquiry.category_suggestion,
            status=inquiry.status,
            draft=DraftData(
                answer_text=answer_text,
                sources=[
                    SourceItem.from_model(s)
                    for s in sources
                ],
            ),
            created_at=inquiry.created_at,
            updated_at=inquiry.updated_at,
        )


# ---------- 초안 수정 ----------

class DraftUpdateRequest(CamelModel):
    answer_text: str = Field(max_length=5000)

    @field_validator("answer_text")
    @classmethod
    def _required(cls, value: str) -> str:
        return _not_blank(value)


class DraftUpdatedData(CamelModel):
    inquiry_id: str
    status: InquiryStatus
    answer_text: str
    updated_at: datetime

    @classmethod
    def from_models(
        cls,
        inquiry: Inquiry,
        draft: AnswerDraft,
    ) -> "DraftUpdatedData":
        return cls(
            inquiry_id=format_public_id(INQUIRY, inquiry.id),
            status=inquiry.status,
            answer_text=draft.edited_text or "",
            updated_at=draft.updated_at,
        )


# ---------- 답변 승인 ----------

class ApproveRequest(CamelModel):
    approved_answer: str = Field(max_length=5000)

    @field_validator("approved_answer")
    @classmethod
    def _required(cls, value: str) -> str:
        return _not_blank(value)


class ApprovedData(CamelModel):
    inquiry_id: str
    status: InquiryStatus
    answered_at: datetime

    @classmethod
    def from_model(
        cls, inquiry: Inquiry
    ) -> "ApprovedData":
        return cls(
            inquiry_id=format_public_id(INQUIRY, inquiry.id),
            status=inquiry.status,
            answered_at=inquiry.answered_at,
        )


# ---------- 상태 변경 ----------

class StatusChangeRequest(CamelModel):
    status: str = Field(
        description="변경할 문의 상태"
    )
    memo: str | None = Field(
        default=None,
        max_length=1000,
        description="담당자 내부 메모",
    )


class StatusChangedData(CamelModel):
    inquiry_id: str
    previous_status: InquiryStatus
    status: InquiryStatus
    updated_at: datetime