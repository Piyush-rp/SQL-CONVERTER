"""Liveness/readiness + Prometheus scrape endpoint. Split into two checks
because a load balancer's liveness probe should never depend on a
downstream database being reachable - only readiness should."""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.core.config import settings
from app.database.session import engine

router = APIRouter(tags=["Health"])


@router.get("/health")
def liveness():
    return {"status": "ok", "version": settings.VERSION}


@router.get("/health/ready")
def readiness():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        return Response(content=f'{{"status": "not_ready", "error": "{exc}"}}', status_code=503, media_type="application/json")


@router.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
