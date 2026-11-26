from collections.abc import Callable
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Path,
    Query,
    status,
)

from app.api.deps import DbSession
from app.core.public_id import INQUIRY, parse_public_id
from app.core.response import ApiResponse, ok
from app.schemas.inquiry import (
    InquiryCreatedData,
    InquiryCreateRequest,
    InquiryStatusData,
)
from app.services import inquiry_service
from app.services.brand_service import get_active_brand


router = APIRouter(
    prefix="/api/v1/inquiries",
    tags=["1:1 문의 (고객)"],
)

DraftScheduler = Callable[[int], None]


def get_draft_scheduler() -> DraftScheduler:
    """테스트에서 AI 실행 함수를 교체할 수 있도록 한다."""
    return inquiry_service.run_ai_draft


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ApiResponse[InquiryCreatedData],
)
def create_inquiry(
    body: InquiryCreateRequest,
    db: DbSession,
    background_tasks: BackgroundTasks,
    schedule_draft: Annotated[
        DraftScheduler,
        Depends(get_draft_scheduler),
    ],
) -> ApiResponse[InquiryCreatedData]:
    brand = get_active_brand(db, body.brand_id)

    inquiry = inquiry_service.create_inquiry(
        db,
        inquiry_service.NewInquiry(
            brand_id=brand.id,
            category_path=body.category_path,
            title=body.title,
            content=body.content,
            customer_name=body.customer_name,
            store_name=body.store_name,
        ),
    )

    # 응답 이후 AI 초안 생성을 시작한다.
    background_tasks.add_task(
        schedule_draft,
        inquiry.id,
    )

    return ok(
        InquiryCreatedData.from_model(inquiry),
        code="INQUIRY_CREATED",
        message="문의가 접수되었습니다.",
        status=status.HTTP_202_ACCEPTED,
    )


@router.get(
    "/{inquiryId}",
    response_model=ApiResponse[InquiryStatusData],
)
def get_inquiry_status(
    db: DbSession,
    inquiry_id: Annotated[
        str,
        Path(
            alias="inquiryId",
            description="문의 ID (예: inq_1001)",
        ),
    ],
    receipt_token: Annotated[
        str | None,
        Query(
            alias="receiptToken",
            description="문의 등록 시 발급한 조회 토큰",
        ),
    ] = None,
) -> ApiResponse[InquiryStatusData]:
    inquiry = inquiry_service.get_inquiry_for_customer(
        db,
        inquiry_id=parse_public_id(INQUIRY, inquiry_id),
        receipt_token=receipt_token,
    )

    return ok(
        InquiryStatusData.from_model(inquiry),
        code="GET_INQUIRY_STATUS_SUCCESS",
        message="문의 처리 상태 조회에 성공했습니다.",
    )