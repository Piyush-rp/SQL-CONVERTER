# Scaling beyond a single instance

The codebase runs correctly as a single instance out of the box. A few
pieces are called out in code comments as "fine for one instance, swap
this for X before running N replicas" - this doc collects them in one
place.

## 1. Schema cache (`app/database/metadata_cache.py`)
Currently an in-process `dict` with a TTL. With multiple backend replicas,
each one introspects and caches independently - correct, just slightly
wasteful, and a schema-cache invalidation (`POST .../schema?refresh=true`)
on one instance won't be seen by the others until their own TTL expires.
**Fix:** back `SchemaCache` with Redis (same `get`/`set`/`invalidate`
interface - the class is intentionally narrow so this is a contained change).

## 2. Rate limiter (`app/dependencies.py::_RateLimiter`)
Same story: an in-process sliding window per user id. With N replicas
behind a load balancer, a user's real limit becomes `N x RATE_LIMIT_PER_MINUTE`
rather than the configured value.
**Fix:** Redis `INCR` + `EXPIRE`, or a library like `slowapi` with a Redis
backend.

## 3. Connection pools (`app/database/connection_manager.py`)
Each replica holds its own SQLAlchemy connection pool per target database
connection. If you have many replicas AND many saved connections, watch
the target databases' `max_connections` - you may need to lower
`pool_size`/`max_overflow` in `app/database/connector.py` accordingly, or
front the target databases with PgBouncer/ProxySQL.

## 4. Query execution thread pool (`app/agents/execution_agent.py`)
Each replica has its own small `ThreadPoolExecutor`. This scales fine
horizontally (more replicas = more capacity) - nothing to change here.

## 5. Background/async work
There isn't any yet (the pipeline is synchronous end-to-end per request).
If query volume grows enough that request-response is too slow for the
UI, the natural next step is to move `POST /ask` to enqueue a job (Celery,
RQ, or Postgres-backed via `SKIP LOCKED`) and have the frontend poll or
subscribe over a websocket for the result, rather than holding the HTTP
connection open for the full agent pipeline.

## 6. Observability
`/metrics` (Prometheus) and structured logs (`app/core/logger.py`) are
already wired up per-instance - point a real Prometheus/Grafana stack or
your APM of choice at them; nothing app-side changes for multi-instance,
you just get one time series per instance/pod (label by instance in your
scrape config).
