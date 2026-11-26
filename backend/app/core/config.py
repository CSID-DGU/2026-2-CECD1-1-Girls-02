from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_name: str = "eVOC API"
    app_env: str = "local"
    app_version: str = "0.1.0"
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_official_collection: str = "brand_a_official_knowledge"
    rag_embedding_model: str = "BAAI/bge-m3"
    rag_top_k: int = 5
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_seconds: float = 20.0
    database_url: str | None = None
    default_brand_code: str = "brand_a"
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
