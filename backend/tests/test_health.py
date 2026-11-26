from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.health import get_health_checks
from app.main import app


@pytest.fixture
def set_checks() -> Iterator[Callable[..., None]]:
    def _set(**states: bool) -> None:
        checks = {
            name: (lambda value=value: value)
            for name, value in states.items()
        }
        app.dependency_overrides[get_health_checks] = (
            lambda: checks
        )

    try:
        yield _set
    finally:
        app.dependency_overrides.pop(
            get_health_checks, None
        )


def test_all_up_is_healthy(set_checks) -> None:
    set_checks(
        database=True,
        aiService=True,
        vectorStore=True,
    )

    response = TestClient(app).get("/healthz")

    assert response.status_code == 200

    body = response.json()

    assert (
        body["status"],
        body["code"],
        body["message"],
    ) == (
        200,
        "HEALTHY",
        "서비스가 정상 동작 중입니다.",
    )

    assert {
        k: body["data"][k]
        for k in (
            "api", "database",
            "aiService", "vectorStore",
        )
    } == {
        "api": "UP",
        "database": "UP",
        "aiService": "UP",
        "vectorStore": "UP",
    }

    assert body["data"]["checkedAt"].endswith("+09:00")


@pytest.mark.parametrize(
    "down",
    ["database", "aiService", "vectorStore"],
)
def test_any_dependency_down_is_503(
    set_checks, down: str
) -> None:
    states = {
        "database": True,
        "aiService": True,
        "vectorStore": True,
        down: False,
    }

    set_checks(**states)

    response = TestClient(app).get("/healthz")

    assert response.status_code == 503

    body = response.json()

    assert body["code"] == "UNHEALTHY"
    assert body["data"][down] == "DOWN"