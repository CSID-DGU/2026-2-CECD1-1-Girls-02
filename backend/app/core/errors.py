from enum import Enum


class ErrorCode(Enum):
    INVALID_REQUEST = (400, "요청 값이 올바르지 않습니다.")
    NOT_FOUND = (404, "요청한 리소스를 찾을 수 없습니다.")
    METHOD_NOT_ALLOWED = (405, "허용되지 않은 요청 방식입니다.")
    CONFLICT = (409, "현재 상태에서 처리할 수 없는 요청입니다.")
    INTERNAL_ERROR = (500, "서버 내부 오류가 발생했습니다.")

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.default_message = message


class AppError(Exception):
    """서비스 로직에서 의도적으로 발생시키는 오류."""

    def __init__(self, error_code: ErrorCode, message: str | None = None) -> None:
        self.error_code = error_code
        self.message = message or error_code.default_message
        super().__init__(self.message)