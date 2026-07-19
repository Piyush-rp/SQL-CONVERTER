"""
FastAPI application entry point. Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
(the Dockerfile/docker-compose do this for you).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.logger import configure_logging, log
from app.database.session import init_metadata_db
from app.middleware.exception_handlers import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware
from app.telemetry.metrics import MetricsMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info(f"Starting {settings.APP_NAME} v{settings.VERSION} ({settings.ENVIRONMENT.value})")
    init_metadata_db()  # dev/demo convenience - use Alembic migrations in real prod deployments
    yield
    log.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT.value != "prod" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_PREFIX)
