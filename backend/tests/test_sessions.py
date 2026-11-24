"""Chat session history: every /ask is saved to a session that can be listed,
reopened, bookmarked, renamed and deleted - and only by its owner."""
from unittest.mock import patch

from app.workflows.workflow_result import WorkflowResult


def _login(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "password": "correcthorse123", "full_name": "T"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "correcthorse123"}).json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _connection(client, headers, path):
    resp = client.post("/api/v1/connections", headers=headers, json={"name": "Shop DB", "engine": "sqlite", "file_path": path})
    return resp.json()["data"]["id"]


def _fake_result(question, session_id):
    return WorkflowResult(
        status="success", question=question, sql="SELECT 1", explanation="ok",
        execution={"columns": ["n"], "rows": [[i] for i in range(300)], "row_count": 300,
                   "execution_time_ms": 1, "truncated": False},
        session_id=session_id or "11111111-2222-3333-4444-555555555555",
    )


def test_ask_saves_to_session_and_history_flow(app_client, target_db_path):
    headers = _login(app_client, "hist@example.com")
    conn_id = _connection(app_client, headers, target_db_path)

    with patch("app.services.query_service.workflow_manager.run",
               side_effect=lambda **kw: _fake_result(kw["question"], kw.get("session_id"))):
        first = app_client.post("/api/v1/ask", headers=headers,
                                json={"connection_id": conn_id, "question": "How many customers are there?"}).json()["data"]
        session_id = first["session_id"]
        app_client.post("/api/v1/ask", headers=headers,
                        json={"connection_id": conn_id, "question": "And by country?", "session_id": session_id})

    sessions = app_client.get("/api/v1/sessions", headers=headers).json()["data"]
    assert len(sessions) == 1
    assert sessions[0]["title"] == "How many customers are there?"
    assert sessions[0]["message_count"] == 2
    assert sessions[0]["connection_name"] == "Shop DB"
    assert sessions[0]["bookmarked"] is False

    detail = app_client.get(f"/api/v1/sessions/{session_id}", headers=headers).json()["data"]
    assert [m["question"] for m in detail["messages"]] == ["How many customers are there?", "And by country?"]
    saved_rows = detail["messages"][0]["response"]["execution"]["rows"]
    assert len(saved_rows) == 200  # capped for storage

    marked = app_client.patch(f"/api/v1/sessions/{session_id}", headers=headers, json={"bookmarked": True}).json()["data"]
    assert marked["bookmarked"] is True
    renamed = app_client.patch(f"/api/v1/sessions/{session_id}", headers=headers, json={"title": "Customer counts"}).json()["data"]
    assert renamed["title"] == "Customer counts"

    # another user can't see or touch it
    other = _login(app_client, "intruder@example.com")
    assert app_client.get(f"/api/v1/sessions/{session_id}", headers=other).status_code == 404
    assert app_client.delete(f"/api/v1/sessions/{session_id}", headers=other).status_code == 404
    assert app_client.get("/api/v1/sessions", headers=other).json()["data"] == []

    assert app_client.delete(f"/api/v1/sessions/{session_id}", headers=headers).status_code == 200
    assert app_client.get("/api/v1/sessions", headers=headers).json()["data"] == []


def test_session_id_of_another_user_is_not_reused(app_client, target_db_path):
    owner = _login(app_client, "owner2@example.com")
    owner_conn = _connection(app_client, owner, target_db_path)
    other = _login(app_client, "other2@example.com")
    other_conn = _connection(app_client, other, target_db_path)

    with patch("app.services.query_service.workflow_manager.run",
               side_effect=lambda **kw: _fake_result(kw["question"], kw.get("session_id"))):
        sid = app_client.post("/api/v1/ask", headers=owner,
                              json={"connection_id": owner_conn, "question": "q1"}).json()["data"]["session_id"]
        hijack = app_client.post("/api/v1/ask", headers=other,
                                 json={"connection_id": other_conn, "question": "q2", "session_id": sid}).json()["data"]

    assert hijack["session_id"] != sid
    owner_detail = app_client.get(f"/api/v1/sessions/{sid}", headers=owner).json()["data"]
    assert [m["question"] for m in owner_detail["messages"]] == ["q1"]
