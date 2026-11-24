from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    status: int
    code: str
    message: str
    data: T | None = None


def ok(
    data: T,
    *,
    code: str = "SUCCESS",
    message: str = "요청이 정상 처리되었습니다.",
    status: int = 200,
) -> ApiResponse[T]:
    return ApiResponse[T](
        status=status,
        code=code,
        message=message,
        data=data,
    )