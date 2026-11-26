"""관리자 대시보드·AI 지표 API (시연용: 인증 생략)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.core.response import ApiResponse, ok
from app.db.models import GenerationPurpose
from app.schemas.metrics import AiMetricsData, DashboardData
from app.services import metrics_service


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["관리자 대시보드 (시연용)"],
)

DateFrom = Annotated[
    date | None,
    Query(
        alias="from",
        description="시작일 (KST). 기본: 최근 30일",
    ),
]

DateTo = Annotated[
    date | None,
    Query(
        alias="to",
        description="종료일 (KST, 포함). 기본: 오늘",
    ),
]


@router.get(
    "/dashboard/summary",
    response_model=ApiResponse[DashboardData],
)
def get_dashboard_summary(
    db: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> ApiResponse[DashboardData]:
    period = metrics_service.resolve_period(
        date_from, date_to
    )

    return ok(
        DashboardData.build(
            period,
            metrics_service.dashboard_summary(db, period),
        ),
        code="GET_ADMIN_DASHBOARD_SUCCESS",
        message="관리자 대시보드 요약 조회에 성공했습니다.",
    )


@router.get(
    "/metrics/ai",
    response_model=ApiResponse[AiMetricsData],
)
def get_ai_metrics(
    db: DbSession,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    purpose: Annotated[
        GenerationPurpose | None,
        Query(
            description=(
                "INQUIRY_DRAFT 또는 CHAT_ANSWER. "
                "없으면 전체"
            )
        ),
    ] = None,
) -> ApiResponse[AiMetricsData]:
    period = metrics_service.resolve_period(
        date_from, date_to
    )

    return ok(
        AiMetricsData.build(
            period,
            purpose,
            metrics_service.ai_metrics(
                db, period, purpose
            ),
        ),
        code="GET_AI_METRICS_SUCCESS",
        message="AI 처리 성능 조회에 성공했습니다.",
    )