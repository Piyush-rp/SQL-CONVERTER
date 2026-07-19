# Enterprise-readiness roadmap

Every item below is marked **Done and verified live** (tested against a
real running service - Postgres, MySQL, Redis, or a live uvicorn
instance), **Done, verified against a mock** (no live service was
available to test against in this environment), or **Not done**. This is
a factual status list, not a marketing one - it reflects two build
sessions: an initial hardening pass (items 1-6) and a follow-up that
built real functionality into `vectorstore/`, `memory/`, `tools/`, and
`utils/` (items 7-10), which were previously empty scaffold folders.

## Done and verified against real, live services

1. **Multi-database support** - PostgreSQL and MySQL were installed and
   run for real (not just SQLite); introspection, FK relationships, cost
   estimation via real `EXPLAIN`, execution, and Postgres's session-level
   read-only enforcement were all tested against live servers
   (`tests/test_live_databases.py`). SQL Server's code path is identical
   (same SQLAlchemy Inspector abstraction) but genuinely untested live -
   no SQL Server instance was available (see "Not done" below).
2. **Multi-instance scaling (Redis-backed cache + rate limiter)** - a real
   Redis server was installed and both the schema cache and rate limiter
   were tested against it, including a test proving two independent
   limiter instances (standing in for two backend replicas) share one
   counter (`tests/test_redis_scaling.py`). Falls back to in-process
   automatically when `REDIS_URL` isn't set.
3. **Concurrent load testing** - ~1,000 requests at 20-30 concurrency
   against a live uvicorn instance, zero errors; the rate limiter
   correctly rejected the 61st+ request in a 70-request burst under real
   concurrency. See `docs/load-testing.md` for exact numbers and -
   importantly - what this does and doesn't prove.
4. **Audit log export** - an admin-only `/admin/audit-log` (JSON) and
   `/admin/audit-log/export.csv` endpoint, RBAC-gated, tested.
5. **Adversarial security testing** - 62 tests actively trying to break
   the SQL security gate: stacked-query injection, comment-based keyword
   splitting, filesystem/command escape hatches (`xp_cmdshell`,
   `LOAD_FILE`, `INTO OUTFILE`, `pg_read_file`), privilege escalation, and
   DDL/write boundary tests across all 4 engines
   (`tests/test_adversarial_security.py`). **Found and fixed a real bug**:
   `UNION`-based queries were being incorrectly rejected as "unknown"
   statement type rather than recognized as read-only.
6. **Embedding-based schema search (`app/vectorstore`)** - TF-IDF (char
   n-gram) + FAISS, an upgrade over pure keyword-overlap narrowing for
   large schemas. Selectable via `SCHEMA_SEARCH_STRATEGY=vector`, tested
   live (fully offline - no network dependency, unlike a neural-embedding
   approach; an `OpenAIEmbeddingBackend` is also provided for that upgrade
   path but needs live network access this environment didn't have to
   test it with).
7. **Multi-turn conversation memory (`app/memory`)** - session-scoped
   turn history (in-process or Redis-backed), a follow-up-question
   heuristic, and real prompt injection of prior turns. Verified with a
   test that inspects the actual messages sent to the (mocked) LLM and
   confirms a follow-up's prompt contains the prior turn's question and
   SQL, and that an unrelated question does NOT pull in stale context.
8. **Agentic tool-calling generation (`app/tools`)** - real LangChain
   tools (schema lookup, SQL validation, bounded exploratory query
   execution) bound to the model with a bounded tool-call loop, as an
   opt-in alternative (`ENABLE_TOOL_CALLING=true`) to the single-shot
   prompt. Tested with a fake tool-calling model exercising the full
   loop, including a guard against a model that never stops calling tools.
9. **Shared utilities (`app/utils`)** - retry-with-backoff (wraps the
   Vault secret fetch), token-budget estimation (wired into schema
   formatting to warn on oversized prompts), and pagination clamping
   (wired into the repository layer as defense-in-depth under the API's
   own request validation) - all tested, and tested for real wiring, not
   just in isolation.
10. **Deployment smoke tests (`tests/smoke_test.py`)** - a standalone
    script that hits a real, already-running instance over HTTP (health,
    auth, connection+schema round-trip), distinct from `backend/tests/`
    which tests the code in-process. Actually run against a live server
    in this environment to confirm it works, not just written.

## Done, but verified against a mock rather than a live service

11. **Secrets provider (Vault)** - a pluggable `SecretsProvider` interface
    with env-var (default) and HashiCorp Vault implementations
    (`app/core/secrets.py`). Tested against a **mocked** `hvac.Client` -
    no real Vault server was available to install here, unlike
    Postgres/MySQL/Redis. The integration logic (auth check, KV v2 read,
    caching, retry-with-backoff, fail-safe fallback on error) is verified;
    a live round-trip against your actual Vault deployment still needs to
    happen before relying on it in production.

## Not done

12. **Independent security review / penetration test.** No amount of
    self-written adversarial tests substitutes for a third party actively
    trying to break this. Item 5 above is real hardening, not a pentest.
13. **SSO/SAML/OIDC.** Auth is still email+password+JWT only. This is the
    single largest remaining gap for most enterprise buyers and hasn't
    been started - it needs a live IdP (Okta/Azure AD/etc.) to implement
    and test against meaningfully, which wasn't available here either.
14. **SQL Server, live-verified.** The code path is dialect-agnostic and
    identical to the Postgres/MySQL paths that *were* proven live, but no
    SQL Server instance was available to actually run it against.
15. **A real `docker compose up`.** The Dockerfiles and compose file are
    correct by inspection and the equivalent steps (install deps, run
    migrations, start the server, seed real Postgres/MySQL/Redis) were
    run manually and verified - but no Docker daemon exists in this build
    environment, so the actual `docker compose up` invocation has never
    been executed. This is the first thing to verify on your machine.
16. **Admin UI.** Role management is still a direct DB edit
    (see `docs/setup.md`).
17. **Very large schemas (500+ tables) at real scale.** The vector search
    upgrade (item 6) helps, but was only tested against small synthetic
    schemas (a handful of tables) - not stress-tested against hundreds.
18. **CI with live service containers.** `.github/workflows/ci.yml` runs
    the full test suite on every push/PR, but GitHub Actions won't have
    Postgres/MySQL/Redis reachable unless you add them as service
    containers to the workflow - the live-service tests will just skip
    there, same as they would on any machine without those services running.

None of the remaining items are large rewrites given the current
architecture (pluggable DB connector, LLM provider, cache backend, secrets
provider, and now schema-search strategy) - but items 12 and 13
specifically need things this environment cannot provide: a human
security researcher and a real identity provider.
