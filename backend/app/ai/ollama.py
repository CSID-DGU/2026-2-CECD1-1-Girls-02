from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaGeneration:
    text: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class OllamaClient:
    """Explicit contract for Ollama's local `/api/generate` endpoint."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_json(self, prompt: str) -> OllamaGeneration:
        payload: dict[str, Any] = {"model": self.model, "prompt": prompt, "stream": False, "format": "json", "options": {"temperature": 0}}
        started = time.perf_counter()
        try:
            response = httpx.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout_seconds)
            response.raise_for_status()
            body = response.json()
            text = body.get("response")
            if not isinstance(text, str) or not text.strip():
                raise OllamaError("Ollama response did not contain a non-empty response field")
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("Ollama generation failed") from exc
        return OllamaGeneration(
            text=text,
            latency_ms=round((time.perf_counter() - started) * 1000),
            prompt_tokens=body.get("prompt_eval_count"),
            completion_tokens=body.get("eval_count"),
        )
