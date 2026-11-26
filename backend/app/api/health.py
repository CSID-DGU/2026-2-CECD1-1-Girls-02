from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.timezone import now_kst
from app.schemas.common import CamelModel
from app.services.health_service import (
    HealthCheck,
    default_checks,
)


router = APIRouter(tags=["Health"])


class HealthData(CamelModel):
    api: str
    database: str
    ai_service: str
    vector_store: str
    checked_at: datetime


def get_health_checks() -> dict[str, HealthCheck]:
    """테스트에서 점검 함수를 교체할 수 있도록 한다."""

    return default_checks()


@router.get("/healthz", response_model=None)
def get_health(
    checks: Annotated[
        dict[str, HealthCheck],
        Depends(get_health_checks),
    ],
) -> JSONResponse:
    results = {
        name: "UP" if check() else "DOWN"
        for name, check in checks.items()
    }

    healthy = all(
        value == "UP"
        for value in results.values()
    )

    data = HealthData(
        api="UP",
        database=results["database"],
        ai_service=results["aiService"],
        vector_store=results["vectorStore"],
        checked_at=now_kst(),
    )

    status = 200 if healthy else 503

    return JSONResponse(
        status_code=status,
        content={
            "status": status,
            "code": (
                "HEALTHY" if healthy else "UNHEALTHY"
            ),
            "message": (
                "서비스가 정상 동작 중입니다."
                if healthy
                else "일부 서비스가 동작하지 않습니다."
            ),
            "data": data.model_dump(
                mode="json",
                by_alias=True,
            ),
        },
    )