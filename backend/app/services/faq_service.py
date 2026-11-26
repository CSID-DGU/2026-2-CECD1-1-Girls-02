from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, contains_eager

from app.core.errors import AppError, ErrorCode
from app.db.models import Faq, FaqCategory


def _active_faqs() -> Select[tuple[Faq]]:
    """활성 FAQ 중 소속 카테고리도 활성인 것만 조회한다."""
    return (
        select(Faq)
        .join(Faq.category)
        .options(contains_eager(Faq.category))
        .where(
            Faq.is_active.is_(True),
            FaqCategory.is_active.is_(True),
        )
    )


def _get_active_category(
    db: Session,
    *,
    brand_id: int,
    code: str,
) -> FaqCategory:
    category = db.scalar(
        select(FaqCategory).where(
            FaqCategory.brand_id == brand_id,
            FaqCategory.code == code,
            FaqCategory.is_active.is_(True),
        )
    )

    if category is None:
        raise AppError(ErrorCode.FAQ_CATEGORY_NOT_FOUND)

    return category


def list_faqs(
    db: Session,
    *,
    brand_id: int,
    category_code: str | None,
    keyword: str | None,
    page: int,
    size: int,
) -> tuple[list[Faq], int]:
    """page는 0부터 시작한다. (목록, 전체 건수)를 반환한다."""
    stmt = _active_faqs().where(Faq.brand_id == brand_id)

    if category_code:
        category = _get_active_category(
            db,
            brand_id=brand_id,
            code=category_code,
        )
        stmt = stmt.where(Faq.category_id == category.id)

    if keyword and keyword.strip():
        word = keyword.strip()
        stmt = stmt.where(
            Faq.question.icontains(word, autoescape=True)
            | Faq.answer.icontains(word, autoescape=True)
        )

    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0

    rows = db.scalars(
        stmt.order_by(FaqCategory.sort_order, Faq.id)
        .offset(page * size)
        .limit(size)
    )

    return list(rows), total


def get_faq(db: Session, faq_id: int) -> Faq:
    faq = db.scalar(
        _active_faqs().where(Faq.id == faq_id)
    )

    if faq is None:
        raise AppError(ErrorCode.FAQ_NOT_FOUND)

    return faq