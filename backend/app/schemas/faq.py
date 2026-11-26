from datetime import datetime

from app.core.public_id import FAQ, format_public_id
from app.db.models import Faq
from app.schemas.common import CamelModel

PREVIEW_LENGTH = 100


def _preview(text: str) -> str:
    """답변 앞부분 미리보기. 줄바꿈·연속 공백은 한 칸으로 줄인다."""
    flat = " ".join(text.split())

    if len(flat) <= PREVIEW_LENGTH:
        return flat

    return flat[:PREVIEW_LENGTH].rstrip() + "…"


class FaqSummary(CamelModel):
    faq_id: str
    category_id: str
    category_name: str
    title: str
    preview: str
    updated_at: datetime

    @classmethod
    def from_model(cls, faq: Faq) -> "FaqSummary":
        return cls(
            faq_id=format_public_id(FAQ, faq.id),
            category_id=faq.category.code,
            category_name=faq.category.name,
            title=faq.question,
            preview=_preview(faq.answer),
            updated_at=faq.updated_at,
        )


class FaqDetail(CamelModel):
    faq_id: str
    category_id: str
    category_name: str
    title: str
    content: str
    updated_at: datetime

    @classmethod
    def from_model(cls, faq: Faq) -> "FaqDetail":
        return cls(
            faq_id=format_public_id(FAQ, faq.id),
            category_id=faq.category.code,
            category_name=faq.category.name,
            title=faq.question,
            content=faq.answer,
            updated_at=faq.updated_at,
        )