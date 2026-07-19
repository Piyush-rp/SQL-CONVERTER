#!/usr/bin/env python3
"""
Deployment smoke test: exercises the critical path against a REAL, already-
running instance (not the in-process TestClient that backend/tests/ uses).
Run this after `docker compose up` or any deployment to confirm the
actual running system works end to end - health, auth, and a connection +
schema round-trip. Does NOT exercise /ask (that needs a real LLM API key
configured on the server, which this script has no way to know about -
see the note it prints instead of silently skipping).

Usage:
    BASE_URL=http://localhost:8000 python tests/smoke_test.py
"""
from __future__ import annotations

import os
import sys
import time
import uuid

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1"

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"

_failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [{_PASS}] {name}")
    else:
        print(f"  [{_FAIL}] {name} {detail}")
        _failures.append(name)


def main() -> int:
    print(f"Running smoke test against {BASE_URL}\n")

    print("1. Health checks")
    try:
        resp = requests.get(f"{API}/health", timeout=5)
        check("GET /health returns 200", resp.status_code == 200, f"(got {resp.status_code})")
    except requests.RequestException as exc:
        check("GET /health returns 200", False, f"(connection failed: {exc})")
        print(f"\nCannot reach {BASE_URL} at all - is the server running? Aborting remaining checks.")
        return 1

    try:
        resp = requests.get(f"{API}/health/ready", timeout=5)
        check("GET /health/ready returns 200 (metadata DB reachable)", resp.status_code == 200, f"(got {resp.status_code})")
    except requests.RequestException as exc:
        check("GET /health/ready returns 200", False, str(exc))

    print("\n2. Auth flow")
    email = f"smoketest-{uuid.uuid4().hex[:8]}@example.com"
    password = "smoketest12345"

    resp = requests.post(f"{API}/auth/register", json={"email": email, "password": password, "full_name": "Smoke Test"})
    check("POST /auth/register succeeds", resp.status_code == 201, f"(got {resp.status_code}: {resp.text[:200]})")

    resp = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    check("POST /auth/login succeeds", resp.status_code == 200, f"(got {resp.status_code})")
    token = resp.json().get("data", {}).get("access_token") if resp.status_code == 200 else None
    check("Login response includes an access token", bool(token))

    if not token:
        print("\nCannot continue without a valid token - aborting remaining checks.")
        _print_summary()
        return 1

    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(f"{API}/auth/me", headers=headers)
    check("GET /auth/me with token succeeds", resp.status_code == 200, f"(got {resp.status_code})")

    resp = requests.get(f"{API}/auth/me")
    check("GET /auth/me without token is rejected (401)", resp.status_code == 401, f"(got {resp.status_code})")

    print("\n3. Connection + schema round-trip (SQLite, no external DB needed)")
    demo_path = os.environ.get("SMOKE_TEST_SQLITE_PATH", "")
    if demo_path:
        resp = requests.post(
            f"{API}/connections", headers=headers,
            json={"name": "smoke-test-db", "engine": "sqlite", "file_path": demo_path, "read_only": True},
        )
        check("POST /connections succeeds", resp.status_code == 201, f"(got {resp.status_code}: {resp.text[:200]})")
        connection_id = resp.json().get("data", {}).get("id") if resp.status_code == 201 else None

        if connection_id:
            resp = requests.get(f"{API}/connections/{connection_id}/schema", headers=headers)
            check("GET .../schema returns table list", resp.status_code == 200 and len(resp.json().get("data", {}).get("tables", [])) > 0)
    else:
        print("  (skipped - set SMOKE_TEST_SQLITE_PATH to a real .sqlite file path on the SERVER to test this)")

    print("\n4. Frontend reachability (if FRONTEND_URL is set)")
    frontend_url = os.environ.get("FRONTEND_URL", "")
    if frontend_url:
        try:
            resp = requests.get(frontend_url, timeout=5)
            check(f"GET {frontend_url} returns 200", resp.status_code == 200, f"(got {resp.status_code})")
        except requests.RequestException as exc:
            check(f"GET {frontend_url} returns 200", False, str(exc))
    else:
        print("  (skipped - set FRONTEND_URL, e.g. http://localhost:8080, to check this)")

    print(
        "\n5. /ask (NL->SQL pipeline) - NOT exercised by this script.\n"
        "   It needs a real LLM API key configured on the server and a\n"
        "   connection to a real target database - both are deployment-\n"
        "   specific. Verify this manually: log into the UI and ask a\n"
        "   real question against a real connection."
    )

    return _print_summary()


def _print_summary() -> int:
    print()
    if _failures:
        print(f"{len(_failures)} check(s) FAILED: {', '.join(_failures)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
