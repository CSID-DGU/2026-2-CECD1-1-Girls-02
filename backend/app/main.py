from fastapi import FastAPI

from app.api.ai_drafts import router as ai_drafts_router
from app.api.health import router as health_router
from app.core.config import get_settings

from app.core.exception_handlers import register_exception_handlers


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url=None,
)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(ai_drafts_router)
