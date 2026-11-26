from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.db.models import Brand


def get_active_brand(db: Session, code: str) -> Brand:
    brand = db.scalar(
        select(Brand).where(
            Brand.code == code,
            Brand.is_active.is_(True),
        )
    )

    if brand is None:
        raise AppError(ErrorCode.BRAND_NOT_FOUND)

    return brand