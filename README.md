# AI SQL Copilot

Ask questions about your database in plain English; get back validated,
executed SQL with an explanation, a chart, and optimization suggestions.

```
"total revenue by month this year"
   -> SELECT date_trunc('month', created_at) AS month, SUM(amount) ...
   -> runs against your database (read-only, row-capped, timed out)
   -> a line chart + results table + a plain-English explanation
```

## Architecture

```
frontend/   React + TypeScript + Tailwind - chat UI, schema browser, charts
backend/    FastAPI + LangGraph multi-agent pipeline + SQLAlchemy
  app/agents/       LangGraph node implementations (one per pipeline stage)
  app/api/          FastAPI routers
  app/auth/         Registration/login business logic
  app/cache/        Schema cache + rate limiter (in-process or Redis-backed)
  app/core/         Config, security, logging, secrets, exceptions
  app/database/     Multi-engine connector, introspection, schema loading
  app/llm/          Provider-agnostic LLM call (OpenAI/Anthropic)
  app/memory/       Multi-turn conversation memory + follow-up detection
  app/models/       SQLAlchemy ORM models (Copilot's own metadata DB)
  app/prompts/      Prompt templates, few-shot examples, prompt builder
  app/schemas/      Pydantic API request/response models, by domain
  app/services/     Thin business-logic layer between routers and everything else
  app/telemetry/    Prometheus metrics
  app/tools/        LangChain tools + the agentic tool-calling generator
  app/utils/        Shared helpers (retry/backoff, pagination, token estimation)
  app/validators/   SQL security gate, syntax validation, cost estimation
  app/vectorstore/  Embedding-based schema search (TF-IDF + FAISS)
  app/workflows/    The LangGraph state machine wiring every agent together
  logs/             Rotating file logs (in addition to stdout)
  tests/            Unit/integration tests - run in-process, no server needed
datasets/   Plain SQL seed data for the demo database (scripts/seed_demo_data.py)
docker/     Shared Docker resources (nginx.conf, dev-mode compose overlay)
docs/       Setup, scaling, load-testing results, and enterprise-readiness roadmap
scripts/    seed_demo_data.py - generates a ready-to-query demo SQLite file
tests/      Deployment SMOKE tests - hit a real, already-running instance over HTTP
```

**The pipeline** (`backend/app/workflows/sql_workflow.py`), one LangGraph
state machine per question:

```
schema → generate → validate ─┬─(valid)──→ execute ─┬─(ok)───────→ optimize → explain → chart → done
                               │                     │
                               ├─(invalid, retries    ├─(fails, retries
                               │  left)→ retry ────┐  │  left)→ retry ─────┐
                               └─(retries exhausted)  └─(timeout/exhausted)│
                                  → rejected/failed       → failed         │
                                                    └──────────────────────┘
                                                       (both retry paths loop
                                                        back to `generate`
                                                        with the error fed
                                                        into the next prompt)
```

Every SQL statement - LLM-generated or not - passes through
`app/validators/sql_security.py` before it can touch a real connection:
single-statement only, AST-classified (not string-matched) statement type,
read-only by default, suspicious-pattern screen for filesystem/exec escape
hatches. Execution is additionally row-capped and wall-clock-timed-out
(`app/agents/execution_agent.py`).

**Database support:** PostgreSQL, MySQL, SQL Server, and SQLite are all
introspected and executed through one dialect-agnostic code path
(`app/database/`) via SQLAlchemy's Inspector - adding a 5th engine is a
~10-line addition to `connector.py`, not a parallel implementation.

**LLM provider:** pluggable per-deployment or per-request between OpenAI
and Anthropic (`app/llm/llm_factory.py`) - set `DEFAULT_LLM_PROVIDER` in
`.env`, or pass `llm_provider` in the `/ask` request body to override it
for a single question.

## Quickstart

See `docs/setup.md` for full instructions. Fastest path:

```bash
cp .env.example .env   # fill in SECRET_KEY + an LLM API key
docker compose up --build
```

Then open http://localhost:8080, register (the first account becomes
admin), add a database connection, and start asking questions.

## Testing

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

**146 tests.** Most (SQL validators, agent pipeline, HTTP API) need no
external services and run anywhere. A subset runs against **real,
live Postgres, MySQL, and Redis** if reachable (auto-skipped otherwise) -
see `docs/setup.md` for standing those up locally. 62 of the 146 are
adversarial security tests that actively try to break the SQL validator
(stacked-query injection, comment-based evasion, filesystem/command escape
hatches, privilege escalation) across all 4 database dialects. Others
cover the embedding-based schema search, multi-turn conversation memory
(including a test that inspects the actual LLM prompt to confirm
follow-up context reaches it), and the agentic tool-calling loop.

## What's genuinely production-grade here vs. what isn't yet

**Real, tested, and working today** - including against live external
services, not just SQLite: the NL→SQL pipeline with bounded
self-correction, the security/validation gate (adversarially tested, one
real bug found and fixed), Postgres + MySQL introspection/execution/cost-
estimation, Redis-backed multi-instance scaling, ~1,000-request concurrent
load testing with zero errors, JWT auth with RBAC, encrypted credentials,
an admin audit-log export, a pluggable secrets provider (Vault, tested
against a mock), embedding-based schema search for large databases,
multi-turn conversation memory, an opt-in agentic tool-calling generation
mode, Alembic migrations, Prometheus metrics, and Docker deployment configs.

**Not yet done** - an independent security audit/pentest, SSO/SAML, a
*live* Vault/SQL-Server verification, and an actual `docker compose up`
(never run here - no Docker daemon in this build environment). Full,
current, honest status of every item: `docs/roadmap.md`.

## License

Add your own - none specified yet.
