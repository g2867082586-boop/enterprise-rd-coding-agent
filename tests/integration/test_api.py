from fastapi.testclient import TestClient

from app.main import app
from app.auth.password import hash_password
from app.auth.service import utcnow
from app.database.models import AppUser
from app.database.session import create_app_session


def admin_client() -> TestClient:
    db = create_app_session()
    now = utcnow()
    db.add(AppUser(id="api-admin", username="apiadmin", email="apiadmin@example.test",
        password_hash=hash_password("Admin12345"), display_name="API Admin", role="admin",
        is_active=True, created_at=now, updated_at=now, last_login_at=None))
    db.commit()
    db.close()
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": "apiadmin", "password": "Admin12345"})
    assert response.status_code == 200
    return client


def test_health_endpoint_reports_modes() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["llm_mode"] == "mock"


def test_agent_and_trace_api_use_real_graph_and_mcp(seeded_database) -> None:
    with admin_client() as client:
        response = client.post("/api/agent/run", json={"query": "ORDER002 是什么？", "session_id": "api-integration"})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "completed"
        assert payload["tool_calls"][0]["tool"] == "search_knowledge_base"
        trace = client.get(f"/api/agent/traces/{payload['request_id']}")
        assert trace.status_code == 200
        assert len(trace.json()["events"]) >= 6


def test_legacy_agent_api_requires_admin() -> None:
    response = TestClient(app).post("/api/agent/run", json={"query": "ORDER002 是什么？"})
    assert response.status_code == 401
