from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import BrandOrDefault, DbSession
from app.core.errors import ErrorCode
from app.core.exception_handlers import field_error_codes
from app.core.response import ApiResponse, ok
from app.schemas.common import Page
from app.schemas.store import StoreItem
from app.services import store_service


router = APIRouter(
    prefix="/api/v1/stores",
    tags=["1:1 문의 (고객)"],
)


@router.get("", response_model=ApiResponse[Page[StoreItem]])
@field_error_codes({
    ("query", "page"): ErrorCode.INVALID_PAGINATION,
    ("query", "size"): ErrorCode.INVALID_PAGINATION,
})
def search_stores(
    brand: BrandOrDefault,
    db: DbSession,
    keyword: Annotated[
        str | None,
        Query(
            max_length=100,
            description="매장명 또는 매장 코드 검색어",
        ),
    ] = None,
    page: Annotated[
        int,
        Query(ge=0, description="0부터 시작"),
    ] = 0,
    size: Annotated[
        int,
        Query(ge=1, le=50),
    ] = 20,
) -> ApiResponse[Page[StoreItem]]:
    stores, total = store_service.search_stores(
        db,
        brand_id=brand.id,
        keyword=keyword,
        page=page,
        size=size,
    )

    return ok(
        Page[StoreItem].of(
            [StoreItem.from_model(s) for s in stores],
            page=page,
            size=size,
            total=total,
        ),
        code="GET_STORES_SUCCESS",
        message="매장 목록 조회에 성공했습니다.",
    )