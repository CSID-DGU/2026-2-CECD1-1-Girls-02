from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import AppError, ErrorCode
from app.core.exception_handlers import (
    field_error_codes,
    register_exception_handlers,
)
from app.main import app as main_app


class _Body(BaseModel):
    title: str
    count: int


def _build_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/app-error")
    async def raise_app_error() -> None:
        raise AppError(
            ErrorCode.NOT_FOUND,
            "문의를 찾을 수 없습니다.",
        )

    @app.get("/query")
    async def needs_int(count: int) -> dict[str, int]:
        return {"count": count}

    @app.post("/body")
    async def needs_body(body: _Body) -> dict[str, str]:
        return {"title": body.title}

    @app.get("/paged")
    @field_error_codes({
        ("query", "page"): ErrorCode.INVALID_PAGINATION
    })
    async def paged(
        page: int = Query(0, ge=0),
        other: int = 0,
    ) -> dict[str, int]:
        return {"page": page}

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


client = TestClient(
    _build_test_app(),
    raise_server_exceptions=False,
)


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


def test_query_error_is_invalid_parameter() -> None:
    response = client.get("/query", params={"count": "abc"})
    assert response.status_code == 400

    body = response.json()
    assert body["code"] == "INVALID_PARAMETER"
    assert body["message"].startswith("query.count")
    assert body["data"] is None


def test_missing_body_field_is_missing_parameter() -> None:
    response = client.post("/body", json={"count": 1})
    assert response.status_code == 400
    assert response.json()["code"] == "MISSING_PARAMETER"


def test_invalid_body_field_is_invalid_input() -> None:
    response = client.post(
        "/body",
        json={"title": "제목", "count": "abc"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_INPUT"


def test_endpoint_override_applies_only_to_listed_field() -> None:
    page_error = client.get(
        "/paged", params={"page": -1}
    ).json()

    assert page_error["code"] == "INVALID_PAGINATION"
    assert page_error["message"] == "페이지 정보가 올바르지 않습니다."

    other_error = client.get(
        "/paged", params={"other": "abc"}
    ).json()

    assert other_error["code"] == "INVALID_PARAMETER"


def test_unknown_route_returns_not_found_envelope() -> None:
    response = client.get("/no-such-path")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


def test_wrong_method_returns_method_not_allowed() -> None:
    response = client.post("/query")
    assert response.status_code == 405
    assert response.json()["code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_error_hides_internal_detail() -> None:
    response = client.get("/boom")
    assert response.status_code == 500

    body = response.json()
    assert body["code"] == "INTERNAL_SERVER_ERROR"
    assert "secret" not in body["message"]