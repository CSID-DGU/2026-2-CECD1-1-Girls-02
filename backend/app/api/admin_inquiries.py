"""관리자 문의 API (시연용: 인증 생략, 외부 공개 금지)."""

from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import DbSession
from app.core.errors import AppError, ErrorCode
from app.core.public_id import (
    INQUIRY,
    format_public_id,
    parse_public_id,
)
from app.core.response import ApiResponse, ok
from app.db.models import InquiryStatus
from app.schemas.admin_inquiry import (
    AdminInquiryDetail,
    AdminInquirySummary,
    ApprovedData,
    ApproveRequest,
    DraftUpdatedData,
    DraftUpdateRequest,
    StatusChangedData,
    StatusChangeRequest,
)
from app.schemas.common import AdminPage
from app.services import admin_inquiry_service as service


router = APIRouter(
    prefix="/api/v1/admin/inquiries",
    tags=["관리자 문의 (시연용)"],
)

InquiryIdPath = Annotated[
    str,
    Path(
        alias="inquiryId",
        description="문의 ID (예: inq_1001)",
    ),
]


def _internal_id(inquiry_id: str) -> int:
    internal = parse_public_id(INQUIRY, inquiry_id)

    if internal is None:
        raise AppError(
            ErrorCode.INVALID_PARAMETER,
            "inquiryId 형식이 올바르지 않습니다.",
        )

    return internal


@router.get(
    "",
    response_model=ApiResponse[AdminPage[AdminInquirySummary]],
)
def list_inquiries(
    db: DbSession,
    status: Annotated[
        InquiryStatus | None,
        Query(description="처리 상태 필터"),
    ] = None,
    category: Annotated[
        str | None,
        Query(
            description="카테고리 코드 필터 "
                        "(하위 분류 포함, 대소문자 무시)"
        ),
    ] = None,
    page: Annotated[
        int,
        Query(ge=1, description="1부터 시작"),
    ] = 1,
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=100),
    ] = 20,
) -> ApiResponse[AdminPage[AdminInquirySummary]]:
    inquiries, total = service.list_inquiries(
        db,
        status=status,
        category=category,
        page=page,
        page_size=page_size,
    )

    return ok(
        AdminPage[AdminInquirySummary](
            items=[
                AdminInquirySummary.from_model(i)
                for i in inquiries
            ],
            page=page,
            page_size=page_size,
            total=total,
        ),
        code="ADMIN_INQUIRY_LIST_SUCCESS",
        message="문의 목록 조회에 성공했습니다.",
    )


@router.get(
    "/{inquiryId}",
    response_model=ApiResponse[AdminInquiryDetail],
)
def get_inquiry(
    db: DbSession,
    inquiry_id: InquiryIdPath,
) -> ApiResponse[AdminInquiryDetail]:
    inquiry = service.get_inquiry(
        db, _internal_id(inquiry_id)
    )

    detail = AdminInquiryDetail.from_model(
        inquiry,
        answer_text=service.answer_text_of(inquiry),
        sources=service.draft_sources(db, inquiry.id),
    )

    return ok(
        detail,
        code="ADMIN_INQUIRY_DETAIL_SUCCESS",
        message="문의 상세 조회에 성공했습니다.",
    )


@router.put(
    "/{inquiryId}/draft",
    response_model=ApiResponse[DraftUpdatedData],
)
def update_draft(
    db: DbSession,
    inquiry_id: InquiryIdPath,
    body: DraftUpdateRequest,
) -> ApiResponse[DraftUpdatedData]:
    inquiry, draft = service.save_draft(
        db,
        _internal_id(inquiry_id),
        body.answer_text,
    )

    return ok(
        DraftUpdatedData.from_models(inquiry, draft),
        code="ADMIN_DRAFT_UPDATED",
        message="답변 초안을 저장했습니다.",
    )


@router.post(
    "/{inquiryId}/approve",
    response_model=ApiResponse[ApprovedData],
)
def approve_answer(
    db: DbSession,
    inquiry_id: InquiryIdPath,
    body: ApproveRequest,
) -> ApiResponse[ApprovedData]:
    inquiry = service.approve_answer(
        db,
        _internal_id(inquiry_id),
        body.approved_answer,
    )

    return ok(
        ApprovedData.from_model(inquiry),
        code="ADMIN_ANSWER_APPROVED",
        message="답변을 등록했습니다.",
    )


@router.patch(
    "/{inquiryId}/status",
    response_model=ApiResponse[StatusChangedData],
)
def change_status(
    db: DbSession,
    inquiry_id: InquiryIdPath,
    body: StatusChangeRequest,
) -> ApiResponse[StatusChangedData]:
    change = service.change_status(
        db,
        _internal_id(inquiry_id),
        body.status,
        body.memo,
    )

    return ok(
        StatusChangedData(
            inquiry_id=format_public_id(
                INQUIRY, change.inquiry.id
            ),
            previous_status=change.previous,
            status=change.inquiry.status,
            updated_at=change.inquiry.updated_at,
        ),
        code="UPDATE_INQUIRY_STATUS_SUCCESS",
        message="문의 상태 변경에 성공했습니다.",
    )