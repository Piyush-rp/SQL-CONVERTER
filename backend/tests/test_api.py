"""HTTP-level tests through FastAPI's TestClient - proves auth, connection
management and the /ask endpoint are correctly wired end-to-end, not just
the underlying services in isolation."""
from unittest.mock import patch


def _register_and_login(client, email="alice@example.com"):
    client.post("/api/v1/auth/register", json={"email": email, "password": "correcthorse123", "full_name": "Alice"})
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "correcthorse123"})
    return resp.json()["data"]["access_token"]


def test_register_login_me(app_client):
    token = _register_and_login(app_client, "bob@example.com")
    resp = app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "bob@example.com"


def test_wrong_password_rejected(app_client):
    app_client.post("/api/v1/auth/register", json={"email": "carol@example.com", "password": "correcthorse123"})
    resp = app_client.post("/api/v1/auth/login", json={"email": "carol@example.com", "password": "wrongpassword"})
    assert resp.status_code == 401
    assert resp.json()["success"] is False


def test_unauthenticated_request_rejected(app_client):
    resp = app_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_create_and_list_connection(app_client, target_db_path):
    token = _register_and_login(app_client, "dave@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = app_client.post(
        "/api/v1/connections",
        headers=headers,
        json={"name": "test-db", "engine": "sqlite", "file_path": target_db_path, "read_only": True},
    )
    assert resp.status_code == 201
    connection_id = resp.json()["data"]["id"]

    resp = app_client.get("/api/v1/connections", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    resp = app_client.get(f"/api/v1/connections/{connection_id}/schema", headers=headers)
    assert resp.status_code == 200
    tables = {t["name"] for t in resp.json()["data"]["tables"]}
    assert tables == {"customers", "orders"}


def test_ask_endpoint_end_to_end(app_client, target_db_path):
    token = _register_and_login(app_client, "erin@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    resp = app_client.post(
        "/api/v1/connections",
        headers=headers,
        json={"name": "test-db-2", "engine": "sqlite", "file_path": target_db_path, "read_only": True},
    )
    connection_id = resp.json()["data"]["id"]

    class GoodModel:
        def invoke(self, messages):
            if any("Explain the following SQL" in m.content for m in messages):
                return type("R", (), {"content": "Counts all customer rows."})()
            return type("R", (), {"content": "```sql\nSELECT COUNT(*) AS n FROM customers\n```"})()

    with patch("app.llm.sql_generator.get_chat_model", return_value=GoodModel()), \
         patch("app.agents.explanation_agent.get_chat_model", return_value=GoodModel()):
        resp = app_client.post(
            "/api/v1/ask", headers=headers,
            json={"connection_id": connection_id, "question": "how many customers are there"},
        )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "success"
    assert data["execution"]["rows"] == [[2]]

    resp = app_client.get("/api/v1/history", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


def _promote_to_admin(email: str) -> None:
    """Mirrors the documented manual-promotion path (docs/setup.md) - used
    here because "first user ever registered" isn't a reliable way to get
    an admin in a test suite where other tests share the same DB session
    and may have already registered users first."""
    from app.database.session import SessionLocal
    from app.models.user import User, UserRole

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.role = UserRole.ADMIN
        db.commit()
    finally:
        db.close()


def test_admin_audit_log_forbidden_for_non_admin(app_client, target_db_path):
    token = _register_and_login(app_client, "regular-viewer-2@example.com")
    resp = app_client.get("/api/v1/admin/audit-log", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_audit_log_visible_to_admin(app_client, target_db_path):
    admin_token = _register_and_login(app_client, "audit-admin@example.com")
    _promote_to_admin("audit-admin@example.com")
    # tokens embed the role at issue time, so re-login after promotion
    admin_token = _register_and_login(app_client, "audit-admin@example.com")
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp = app_client.post(
        "/api/v1/connections", headers=headers,
        json={"name": "audit-test-db", "engine": "sqlite", "file_path": target_db_path, "read_only": True},
    )
    connection_id = resp.json()["data"]["id"]

    with patch("app.llm.sql_generator.get_chat_model", return_value=type("M", (), {
        "invoke": lambda self, m: type("R", (), {"content": "```sql\nSELECT COUNT(*) AS n FROM customers\n```"})()
    })()), patch("app.agents.explanation_agent.get_chat_model", return_value=type("M", (), {
        "invoke": lambda self, m: type("R", (), {"content": "explained"})()
    })()):
        app_client.post("/api/v1/ask", headers=headers, json={"connection_id": connection_id, "question": "how many customers"})

    resp = app_client.get("/api/v1/admin/audit-log", headers=headers)
    assert resp.status_code == 200
    entries = resp.json()["data"]
    assert len(entries) >= 1
    assert entries[0]["user_email"] == "audit-admin@example.com"

    resp = app_client.get("/api/v1/admin/audit-log/export.csv", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "audit-admin@example.com" in resp.text
