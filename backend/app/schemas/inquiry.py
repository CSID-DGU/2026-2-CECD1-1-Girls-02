from datetime import datetime

from pydantic import Field, field_validator

from app.core.public_id import INQUIRY, format_public_id
from app.db.models import Inquiry, InquiryStatus, InquiryType
from app.schemas.common import CamelModel
from app.services.inquiry_service import (
    STATUS_LABELS,
    final_answer_of,
)


def _not_blank(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("비어 있을 수 없습니다.")

    return value


class InquiryCreateRequest(CamelModel):
    brand_id: str = Field(
        description="가상 브랜드 ID (예: brand_a)"
    )
    category_path: list[str] | None = Field(
        default=None,
        description="고객이 선택한 문의 분류 경로",
    )
    title: str = Field(max_length=200)
    content: str = Field(max_length=5000)
    customer_name: str = Field(
        max_length=50,
        description="고객 표시 이름. 가상 데이터 사용 권장",
    )
    store_name: str | None = Field(
        default=None,
        max_length=100,
    )
    privacy_consent: bool

    @field_validator("title", "content", "customer_name")
    @classmethod
    def _required_text(cls, value: str) -> str:
        return _not_blank(value)

    @field_validator("privacy_consent")
    @classmethod
    def _must_consent(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError(
                "개인정보 수집·이용에 동의해야 합니다."
            )

        return value


class InquiryCreatedData(CamelModel):
    inquiry_id: str
    receipt_token: str
    status: InquiryStatus
    created_at: datetime

    @classmethod
    def from_model(
        cls, inquiry: Inquiry
    ) -> "InquiryCreatedData":
        return cls(
            inquiry_id=format_public_id(INQUIRY, inquiry.id),
            receipt_token=inquiry.receipt_token,
            status=inquiry.status,
            created_at=inquiry.created_at,
        )


class InquiryStatusData(CamelModel):
    inquiry_id: str
    title: str
    inquiry_type: InquiryType
    status: InquiryStatus
    status_label: str
    created_at: datetime
    answered_at: datetime | None
    final_answer: str | None

    @classmethod
    def from_model(
        cls, inquiry: Inquiry
    ) -> "InquiryStatusData":
        final_answer = final_answer_of(inquiry)

        return cls(
            inquiry_id=format_public_id(INQUIRY, inquiry.id),
            title=inquiry.title,
            inquiry_type=inquiry.inquiry_type,
            status=inquiry.status,
            status_label=STATUS_LABELS[inquiry.status],
            created_at=inquiry.created_at,
            answered_at=(
                inquiry.answered_at
                if final_answer is not None
                else None
            ),
            final_answer=final_answer,
        )