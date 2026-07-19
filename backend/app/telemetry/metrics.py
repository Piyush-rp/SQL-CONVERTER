"""
Prometheus instrumentation. Exposed at GET /metrics (see api/health.py) for
scraping by any standard Prometheus/Grafana/Datadog-agent setup - this is
the piece that turns "it runs" into "we can see how it's running in prod":
request rates, latencies, and NL->SQL pipeline outcomes by status.
"""
from __future__ import annotations

import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "path"]
)
NL2SQL_REQUESTS_TOTAL = Counter(
    "nl2sql_requests_total", "NL-to-SQL pipeline outcomes", ["status"]
)
NL2SQL_RETRY_COUNT = Histogram(
    "nl2sql_retry_count", "Number of self-correction retries per question"
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        # Avoid unbounded cardinality from path params (e.g. /connections/{id})
        # by using the matched route template rather than the raw path.
        route = request.scope.get("route")
        path_label = route.path if route is not None else request.url.path

        HTTP_REQUESTS_TOTAL.labels(request.method, path_label, response.status_code).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(request.method, path_label).observe(duration)
        return response


def record_nl2sql_outcome(status: str, retry_count: int) -> None:
    NL2SQL_REQUESTS_TOTAL.labels(status).inc()
    NL2SQL_RETRY_COUNT.observe(retry_count)
