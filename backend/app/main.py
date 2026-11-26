from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai_drafts import router as ai_drafts_router
from app.api.health import router as health_router
from app.core.config import get_settings
from app.api.faqs import router as faqs_router
from app.api.inquiry_categories import router as inquiry_categories_router
from app.api.stores import router as stores_router

from app.core.exception_handlers import register_exception_handlers


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url=None,
)

cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(ai_drafts_router)
app.include_router(faqs_router)
app.include_router(inquiry_categories_router)
app.include_router(stores_router)
