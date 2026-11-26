"""여러 라우터가 공유하는 FastAPI 의존성."""
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Brand
from app.db.session import get_db
from app.services.brand_service import get_active_brand

DbSession = Annotated[Session, Depends(get_db)]


def get_required_brand(
    db: DbSession,
    x_brand_code: Annotated[
        str,
        Header(
            alias="X-Brand-Code",
            description="브랜드 코드 (예: brand_a)",
        ),
    ],
) -> Brand:
    """X-Brand-Code 헤더가 필수인 API용."""
    return get_active_brand(db, x_brand_code)


def get_brand_or_default(
    db: DbSession,
    x_brand_code: Annotated[
        str | None,
        Header(
            alias="X-Brand-Code",
            description="브랜드 코드. 없으면 기본 브랜드 사용",
        ),
    ] = None,
) -> Brand:
    """헤더가 없으면 기본 브랜드를 쓴다."""
    return get_active_brand(
        db,
        x_brand_code or get_settings().default_brand_code,
    )


RequiredBrand = Annotated[Brand, Depends(get_required_brand)]
BrandOrDefault = Annotated[Brand, Depends(get_brand_or_default)]