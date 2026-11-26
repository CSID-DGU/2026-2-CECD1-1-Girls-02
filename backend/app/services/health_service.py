"""DB·Ollama·Chroma 의존 서비스 상태 점검."""

from collections.abc import Callable

import httpx
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_engine


TIMEOUT_SECONDS = 2.0

HealthCheck = Callable[[], bool]


def check_database() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))

        return True

    except Exception:
        return False


def check_ollama() -> bool:
    try:
        base_url = (
            get_settings().ollama_base_url.rstrip("/")
        )

        response = httpx.get(
            f"{base_url}/api/tags",
            timeout=TIMEOUT_SECONDS,
        )

        return response.status_code == 200

    except httpx.HTTPError:
        return False


def check_chroma() -> bool:
    settings = get_settings()

    try:
        response = httpx.get(
            f"http://{settings.chroma_host}:"
            f"{settings.chroma_port}/api/v2/heartbeat",
            timeout=TIMEOUT_SECONDS,
        )

        return response.status_code == 200

    except httpx.HTTPError:
        return False


def default_checks() -> dict[str, HealthCheck]:
    return {
        "database": check_database,
        "aiService": check_ollama,
        "vectorStore": check_chroma,
    }