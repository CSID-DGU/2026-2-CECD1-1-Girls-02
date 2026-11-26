from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import DbSession, RequiredBrand
from app.core.errors import AppError, ErrorCode
from app.core.exception_handlers import field_error_codes
from app.core.public_id import FAQ, parse_public_id
from app.core.response import ApiResponse, ok
from app.schemas.common import Page
from app.schemas.faq import FaqDetail, FaqSummary
from app.services import faq_service


router = APIRouter(
    prefix="/api/v1/faqs",
    tags=["FAQ (고객)"],
)


@router.get("", response_model=ApiResponse[Page[FaqSummary]])
@field_error_codes({
    ("query", "page"): ErrorCode.INVALID_PAGINATION,
    ("query", "size"): ErrorCode.INVALID_PAGINATION,
})
def list_faqs(
    brand: RequiredBrand,
    db: DbSession,
    category_id: Annotated[
        str | None,
        Query(alias="categoryId", description="FAQ 카테고리 ID (예: faq_event)"),
    ] = None,
    keyword: Annotated[
        str | None,
        Query(max_length=100, description="검색어 (제목·내용)"),
    ] = None,
    page: Annotated[int, Query(ge=0, description="0부터 시작")] = 0,
    size: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ApiResponse[Page[FaqSummary]]:
    faqs, total = faq_service.list_faqs(
        db,
        brand_id=brand.id,
        category_code=category_id,
        keyword=keyword,
        page=page,
        size=size,
    )

    return ok(
        Page[FaqSummary].of(
            [FaqSummary.from_model(f) for f in faqs],
            page=page,
            size=size,
            total=total,
        ),
        code="GET_FAQS_SUCCESS",
        message="FAQ 목록 조회에 성공했습니다.",
    )


@router.get("/{faqId}", response_model=ApiResponse[FaqDetail])
def get_faq(
    db: DbSession,
    faq_id: Annotated[
        str,
        Path(alias="faqId", description="FAQ ID (예: faq_001)"),
    ],
) -> ApiResponse[FaqDetail]:
    internal_id = parse_public_id(FAQ, faq_id)

    if internal_id is None:
        raise AppError(ErrorCode.FAQ_NOT_FOUND)

    return ok(
        FaqDetail.from_model(
            faq_service.get_faq(db, internal_id)
        ),
        code="GET_FAQ_DETAIL_SUCCESS",
        message="FAQ 상세 조회에 성공했습니다.",
    )