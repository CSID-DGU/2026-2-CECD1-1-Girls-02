from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Store


def search_stores(
    db: Session,
    *,
    brand_id: int,
    keyword: str | None,
    page: int,
    size: int,
) -> tuple[list[Store], int]:
    """매장명 또는 매장 코드로 검색한다."""
    stmt = select(Store).where(
        Store.brand_id == brand_id
    )

    if keyword and keyword.strip():
        word = keyword.strip()

        stmt = stmt.where(
            Store.name.icontains(word, autoescape=True)
            | Store.code.icontains(word, autoescape=True)
        )

    total = db.scalar(
        select(func.count()).select_from(stmt.subquery())
    ) or 0

    rows = db.scalars(
        stmt.order_by(
            Store.is_active.desc(),
            Store.name,
            Store.id,
        )
        .offset(page * size)
        .limit(size)
    )

    return list(rows), total