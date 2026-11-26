from enum import Enum


class ErrorCode(Enum):
    """API 명세의 에러 코드. 이름이 그대로 응답의 `code`가 된다."""

    # 400: 입력 오류
    MISSING_PARAMETER = (400, "필수 항목이 누락되었습니다.")
    INVALID_INPUT = (400, "입력 값이 올바르지 않습니다.")
    INVALID_PARAMETER = (400, "요청 파라미터가 올바르지 않습니다.")
    INVALID_PAGINATION = (400, "페이지 정보가 올바르지 않습니다.")

    # 404 / 405 / 409: 공통
    NOT_FOUND = (404, "요청한 리소스를 찾을 수 없습니다.")
    METHOD_NOT_ALLOWED = (405, "허용되지 않은 요청 방식입니다.")
    CONFLICT = (409, "현재 상태에서 처리할 수 없는 요청입니다.")
    BRAND_NOT_FOUND = (404, "브랜드를 찾을 수 없습니다.")
    
    # FAQ
    FAQ_CATEGORY_NOT_FOUND = (404, "FAQ 카테고리를 찾을 수 없습니다.")
    FAQ_NOT_FOUND = (404, "FAQ를 찾을 수 없습니다.")

    # 1:1 문의
    MISSING_RECEIPT_TOKEN = (400, "조회 토큰이 필요합니다.")
    INVALID_RECEIPT_TOKEN = (403, "조회 토큰이 문의와 일치하지 않습니다.")
    INQUIRY_NOT_FOUND = (404, "문의를 찾을 수 없습니다.")
    INQUIRY_SAVE_FAILED = (500, "문의 저장에 실패했습니다.")

    # 관리자 문의 처리
    INVALID_STATUS = (400, "허용하지 않는 상태값입니다.")
    INQUIRY_ALREADY_ANSWERED = (409, "이미 답변이 완료된 문의입니다.")
    INVALID_STATUS_TRANSITION = (409, "현재 상태에서 허용하지 않는 처리입니다.")

    # 500
    INTERNAL_SERVER_ERROR = (500, "서버 내부 오류가 발생했습니다.")

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.default_message = message


class AppError(Exception):
    """서비스 로직에서 의도적으로 발생시키는 오류."""

    def __init__(self, error_code: ErrorCode, message: str | None = None) -> None:
        self.error_code = error_code
        self.message = message or error_code.default_message
        super().__init__(self.message)