# tests/ (deployment smoke tests)

Not to be confused with `backend/tests/` (unit/integration tests that run
against the code in-process, no running server needed - what CI runs on
every PR). This folder holds smoke tests that hit a REAL, already-running
deployment over HTTP - run these after `docker compose up` (or any other
deployment) to verify the actual running instance works, as opposed to
verifying the code is correct in isolation.

```bash
pip install requests
BASE_URL=http://localhost:8000 python tests/smoke_test.py
```

Defaults to `http://localhost:8000` if `BASE_URL` isn't set. Exits
non-zero on any failure, so it's usable as a post-deploy CI gate
(`docker compose up -d && python tests/smoke_test.py || rollback`).
