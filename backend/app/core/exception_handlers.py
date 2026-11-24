import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode

logger = logging.getLogger(__name__)

_HTTP_STATUS_TO_CODE = {
    400: ErrorCode.INVALID_REQUEST,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.CONFLICT,
}


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


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc.error_code.status, exc.error_code.name, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first.get("loc", ()))
        message = f"{location}: {first.get('msg', '')}" if location else ErrorCode.INVALID_REQUEST.default_message
        return _error_response(400, ErrorCode.INVALID_REQUEST.name, message)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        error_code = _HTTP_STATUS_TO_CODE.get(exc.status_code)
        if error_code is None:
            return _error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))
        return _error_response(exc.status_code, error_code.name, error_code.default_message)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error")
        return _error_response(500, ErrorCode.INTERNAL_ERROR.name, ErrorCode.INTERNAL_ERROR.default_message)