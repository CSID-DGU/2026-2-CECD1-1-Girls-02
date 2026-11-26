"""모든 오류를 `{status, code, message, data: null}` 형식으로 응답한다.

입력값 검증 오류(RequestValidationError)의 code 결정 규칙:
1. 엔드포인트에 `@field_error_codes`로 지정한 필드면 그 코드
2. body 필수 항목 누락 -> MISSING_PARAMETER
3. body 값 오류 -> INVALID_INPUT
4. query / path / header 값 오류 -> INVALID_PARAMETER
"""

import logging
from collections.abc import Callable, Mapping
from typing import Any, TypeVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

FieldKey = tuple[str, str]
F = TypeVar("F", bound=Callable[..., Any])

_HTTP_STATUS_TO_CODE = {
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
}


def field_error_codes(mapping: Mapping[FieldKey, ErrorCode]) -> Callable[[F], F]:
    """엔드포인트별로 특정 필드의 입력 오류 code를 지정한다.

    예: @field_error_codes({("query", "page"): ErrorCode.INVALID_PAGINATION})
    """

    def decorator(endpoint: F) -> F:
        endpoint.__field_error_codes__ = dict(mapping)  # type: ignore[attr-defined]
        return endpoint

    return decorator


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "status": status,
            "code": code,
            "message": message,
            "data": None,
        },
    )


def _default_validation_code(error: Mapping[str, Any]) -> ErrorCode:
    loc = error.get("loc", ())
    if loc and loc[0] == "body":
        return (
            ErrorCode.MISSING_PARAMETER
            if error.get("type") == "missing"
            else ErrorCode.INVALID_INPUT
        )
    return ErrorCode.INVALID_PARAMETER


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(
            exc.error_code.status,
            exc.error_code.name,
            exc.message,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        endpoint = request.scope.get("endpoint")
        overrides: Mapping[FieldKey, ErrorCode] = getattr(
            endpoint, "__field_error_codes__", {}
        )

        field = tuple(str(part) for part in first.get("loc", ()))[:2]
        if field in overrides:
            override = overrides[field]
            return _error_response(
                override.status,
                override.name,
                override.default_message,
            )

        code = _default_validation_code(first)
        location = ".".join(str(part) for part in first.get("loc", ()))
        message = (
            f"{location}: {first.get('msg', '')}"
            if location
            else code.default_message
        )
        return _error_response(code.status, code.name, message)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        error_code = _HTTP_STATUS_TO_CODE.get(exc.status_code)
        if error_code is None:
            return _error_response(
                exc.status_code,
                "HTTP_ERROR",
                str(exc.detail),
            )
        return _error_response(
            exc.status_code,
            error_code.name,
            error_code.default_message,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        _: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled server error")
        error_code = ErrorCode.INTERNAL_SERVER_ERROR
        return _error_response(
            error_code.status,
            error_code.name,
            error_code.default_message,
        )