from fastapi import APIRouter

from app.api.deps import BrandOrDefault, DbSession
from app.core.response import ApiResponse, ok
from app.schemas.inquiry_category import (
    CategoryItem,
    InquiryCategoriesData,
    InquiryTypeItem,
)
from app.services import inquiry_category_service as service


router = APIRouter(
    prefix="/api/v1/inquiry-categories",
    tags=["1:1 문의 (고객)"],
)


@router.get(
    "",
    response_model=ApiResponse[InquiryCategoriesData],
    response_model_exclude_none=True,
)
def get_inquiry_categories(
    brand: BrandOrDefault,
    db: DbSession,
) -> ApiResponse[InquiryCategoriesData]:
    data = InquiryCategoriesData(
        inquiry_types=[
            InquiryTypeItem(code=code.value, name=name)
            for code, name in service.INQUIRY_TYPE_NAMES.items()
        ],
        categories=[
            CategoryItem.from_node(node)
            for node in service.get_category_tree(
                db, brand_id=brand.id
            )
        ],
    )

    return ok(
        data,
        code="GET_INQUIRY_CATEGORIES_SUCCESS",
        message="문의 카테고리 조회에 성공했습니다.",
    )