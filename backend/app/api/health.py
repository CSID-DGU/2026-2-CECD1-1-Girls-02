from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(tags=["Health"])


class HealthData(BaseModel):
    api: str


class HealthResponse(BaseModel):
    status: int
    code: str
    message: str
    data: HealthData


@router.get("/healthz", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(
        status=200,
        code="HEALTHY",
        message="서비스가 정상 동작 중입니다.",
        data=HealthData(api="UP"),
    )
