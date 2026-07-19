# Load testing - what was actually measured

This isn't a claim about your production hardware or network - it's the
real, measured behavior of this codebase, run against a live uvicorn
instance (single worker) on the sandbox machine this was built in, with
SQLite as both the metadata DB and the target DB, and a real Redis
instance backing the rate limiter. Numbers will differ (likely better)
against Postgres + real hardware + multiple workers, but this is honest
evidence the app behaves correctly under concurrency, not just in theory.

## What was tested

| Endpoint | Requests | Concurrency | Success | Throughput | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| `/health` (baseline) | 200 | 20 | 200/200 | 212 req/s | 28ms | 578ms* | 618ms* |
| `/connections/{id}/schema` (real introspection) | 200 | 20 | 200/200 | 243 req/s | 74ms | 133ms | 144ms |
| `/connections` (auth + DB query) | 300 | 30 | 300/300 | 288 req/s | 96ms | 156ms | 159ms |
| `/history` (auth + DB query) | 300 | 30 | 300/300 | 301 req/s | 96ms | 124ms | 130ms |

\* The health-check p95/p99 spike is thread-pool warm-up on the very first
burst of connections, not a steady-state number - later endpoints (which
ran after the pool was warm) show the more representative ~100-150ms tail.

**Zero errors, zero dropped requests** across ~1,000 requests at 20-30
concurrent connections on a single worker process.

## Rate limiter, verified under real concurrent load

70 simultaneous `POST /ask` calls against the default 60/minute limit,
backed by the real Redis-based limiter (`app/dependencies.py::_RedisRateLimiter`):

```
Counter({502: 60, 429: 10})
```

The first 60 went through (502 = no LLM API key configured in this test
run, expected - the *pipeline*, not the *limiter*, is what returned that);
the remaining 10 were correctly rejected with `429 Too Many Requests`.
This confirms the limiter's count is accurate even under genuine
concurrent bursts, not just sequential requests.

## What this does and doesn't prove

**Proves:** the app doesn't fall over, deadlock, or miscount under
concurrent load; the DB connection pool and Redis-backed rate limiter
behave correctly under contention; baseline latency for non-LLM endpoints
is good (sub-100ms p50).

**Doesn't prove:** end-to-end `/ask` latency under load, since that's
dominated by the LLM provider's response time (typically 1-5s+ per call,
entirely outside this app's control) - that's a capacity-planning input
you'll need to measure with your own API key and provider, not something
a sandbox without one can honestly report. It also doesn't test multi-day
stability, memory growth, or behavior under the kind of traffic spikes and
network conditions a real production load balancer would see.
