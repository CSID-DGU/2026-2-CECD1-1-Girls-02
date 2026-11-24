from fastapi import APIRouter
from pydantic import BaseModel

from app.core.response import ApiResponse, ok


router = APIRouter(tags=["Health"])


class HealthData(BaseModel):
    api: str



@router.get("/healthz", response_model=ApiResponse[HealthData])
async def get_health() -> ApiResponse[HealthData]:
    return ok(
        HealthData(api="UP"),
        code="HEALTHY",
        message="서비스가 정상 동작 중입니다.",
    )
