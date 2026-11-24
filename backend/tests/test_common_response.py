from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import AppError, ErrorCode
from app.core.exception_handlers import register_exception_handlers
from app.main import app as main_app


def _build_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    async def raise_app_error() -> None:
        raise AppError(ErrorCode.NOT_FOUND, "문의를 찾을 수 없습니다.")

    @app.get("/validation")
    async def needs_int(page: int) -> dict[str, int]:
        return {"page": page}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


client = TestClient(_build_test_app(), raise_server_exceptions=False)


def test_health_uses_envelope() -> None:
    body = TestClient(main_app).get("/healthz").json()
    assert body == {
        "status": 200,
        "code": "HEALTHY",
        "message": "서비스가 정상 동작 중입니다.",
        "data": {"api": "UP"},
    }


def test_app_error_returns_envelope_with_null_data() -> None:
    response = client.get("/app-error")
    assert response.status_code == 404
    assert response.json() == {
        "status": 404,
        "code": "NOT_FOUND",
        "message": "문의를 찾을 수 없습니다.",
        "data": None,
    }


def test_validation_error_is_400_invalid_request() -> None:
    response = client.get("/validation", params={"page": "abc"})
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "INVALID_REQUEST"
    assert body["message"].startswith("query.page")
    assert body["data"] is None


def test_unknown_route_returns_not_found_envelope() -> None:
    response = client.get("/no-such-path")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_unexpected_error_hides_internal_detail() -> None:
    response = client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert "secret" not in body["message"]