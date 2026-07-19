"""
Binds a request_id (from the incoming X-Request-ID header, or a fresh uuid4)
into contextvars for the duration of the request, so every log line emitted
while handling it - across FastAPI, the workflow, and every agent - carries
the same id. Also logs method/path/status/duration for every request.
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logger import log, request_id_ctx, user_id_ctx


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        user_token = user_id_ctx.set("-")

        start = time.monotonic()
        try:
            response = await call_next(request)
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            request_id_ctx.reset(token)
            user_id_ctx.reset(user_token)

        response.headers["X-Request-ID"] = request_id
        log.bind().info(
            f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms) req={request_id}"
        )
        return response
