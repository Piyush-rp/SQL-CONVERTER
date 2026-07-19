"""Registers a single exception handler that turns every AppError subclass
into the standard APIResponse envelope with the right status code, and
falls back to a generic 500 (never leaking a traceback) for anything else."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.core.logger import log
from app.core.responses import APIResponse


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=APIResponse.fail(exc.error_code, exc.message, exc.details).model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        log.exception(f"Unhandled exception on {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content=APIResponse.fail("internal_error", "An unexpected error occurred").model_dump(),
        )
