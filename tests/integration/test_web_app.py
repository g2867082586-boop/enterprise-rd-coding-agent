from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.models import AppUser, ApprovalRequest, ChatMessage, UserSession
from app.config import get_settings
from app.agent.approval_workflow import get_approval_graph
from app.database.session import create_app_session
from app.main import app


def register(client: TestClient, username: str, email: str) -> dict:
    response = client.post("/api/auth/register", json={
        "username": username, "email": email, "password": "Example123", "display_name": username,
    })
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, username: str, password: str = "Example123") -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    assert response.cookies.get("nebula_session")


def test_register_login_me_logout_and_session_revocation() -> None:
    with TestClient(app) as client:
        user = register(client, "webuser", "webuser@example.test")
        assert "password" not in user and "password_hash" not in user
        assert client.post("/api/auth/register", json={
            "username": "webuser", "email": "other@example.test", "password": "Example123",
            "display_name": "Other",
        }).status_code == 409
        assert client.post("/api/auth/register", json={
            "username": "anotheruser", "email": "webuser@example.test", "password": "Example123",
            "display_name": "Other",
        }).status_code == 409
        assert client.post("/api/auth/login", json={
            "username": "webuser", "password": "incorrect",
        }).status_code == 401
        login(client, "webuser")
        assert client.get("/api/auth/me").json()["username"] == "webuser"
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401
        db = create_app_session()
        session = db.scalar(select(UserSession))
        assert session and session.revoked_at is not None
        db.close()


def test_disabled_user_cannot_login() -> None:
    with TestClient(app) as client:
        register(client, "disabled", "disabled@example.test")
        db = create_app_session()
        user = db.scalar(select(AppUser).where(AppUser.username == "disabled"))
        user.is_active = False
        db.commit()
        db.close()
        response = client.post("/api/auth/login", json={"username": "disabled", "password": "Example123"})
        assert response.status_code == 401
        assert response.json()["detail"] == "用户名或密码错误"


def test_chat_agent_history_trace_ownership_and_logout(seeded_database) -> None:
    with TestClient(app) as alice:
        register(alice, "aliceweb", "aliceweb@example.test")
        login(alice, "aliceweb")
        created = alice.post("/api/chat/sessions", json={"title": "新对话"})
        assert created.status_code == 201
        session_id = created.json()["id"]
        answer = alice.post(f"/api/chat/sessions/{session_id}/messages", json={
            "content": "用户登录接口需要哪些参数？登录失败时应该如何排查？"
        })
        assert answer.status_code == 200, answer.text
        result = answer.json()
        assert result["answer"]
        assert result["sources"]
        assert result["runtime_mode"]["llm"] == "mock"
        detail = alice.get(f"/api/chat/sessions/{session_id}")
        assert [m["role"] for m in detail.json()["messages"]] == ["user", "assistant"]
        traces = alice.get("/api/traces").json()
        assert traces[0]["request_id"] == result["request_id"]

        with TestClient(app) as bob:
            register(bob, "bobweb", "bobweb@example.test")
            login(bob, "bobweb")
            assert bob.get(f"/api/chat/sessions/{session_id}").status_code == 404
            assert bob.get(f"/api/traces/{result['request_id']}").status_code == 404
            assert bob.post("/api/knowledge/rebuild").status_code == 403

        db = create_app_session()
        assert db.scalar(select(ChatMessage).where(ChatMessage.request_id == result["request_id"]))
        db.close()


def test_admin_approval_is_idempotent_and_resumes_server_owned_action(tmp_path) -> None:
    settings = get_settings()
    enterprise = tmp_path / "enterprise"; enterprise.mkdir()
    (enterprise / "policy.md").write_text("# 内部规范\n受控导入测试文档。", encoding="utf-8")
    settings.enterprise_knowledge_dir = str(enterprise)
    settings.knowledge_index_path = str(tmp_path / "approval-index.json")
    with TestClient(app) as client:
        register(client, "approver", "approver@example.test")
        db = create_app_session(); user = db.scalar(select(AppUser).where(AppUser.username == "approver")); user.role = "admin"; db.commit(); db.close()
        login(client, "approver")
        created = client.post("/api/knowledge/rebuild")
        assert created.status_code == 202
        approval_id = created.json()["id"]
        thread_id = created.json()["thread_id"]
        paused = get_approval_graph().get_state({"configurable": {"thread_id": thread_id}})
        assert paused.values["approval_status"] == "pending"
        assert paused.next == ("human_approval",)
        first = client.post(f"/api/approvals/{approval_id}/approve", json={"reason": "reviewed"})
        second = client.post(f"/api/approvals/{approval_id}/approve", json={"reason": "ignored duplicate"})
        assert first.status_code == second.status_code == 200
        assert second.json()["decision_reason"] == "reviewed"
        resumed = client.post(f"/api/approvals/{approval_id}/resume")
        duplicate = client.post(f"/api/approvals/{approval_id}/resume")
        assert resumed.status_code == duplicate.status_code == 200
        assert duplicate.json()["status"] == "completed"
        completed = get_approval_graph().get_state({"configurable": {"thread_id": thread_id}})
        assert completed.values["approval_status"] == "approved"
        assert completed.next == ()
        db = create_app_session(); row = db.get(ApprovalRequest, approval_id)
        assert row and row.thread_id and '"approval_status": "pending"' in row.checkpoint_json
        db.close()
        rejected_created = client.post("/api/knowledge/rebuild").json()
        rejected_id, rejected_thread = rejected_created["id"], rejected_created["thread_id"]
        rejected = client.post(f"/api/approvals/{rejected_id}/reject", json={"reason": "unsafe"})
        duplicate_reject = client.post(f"/api/approvals/{rejected_id}/reject", json={"reason": "duplicate"})
        assert rejected.status_code == duplicate_reject.status_code == 200
        assert duplicate_reject.json()["decision_reason"] == "unsafe"
        assert client.post(f"/api/approvals/{rejected_id}/resume").status_code == 409
        rejected_state = get_approval_graph().get_state({"configurable": {"thread_id": rejected_thread}})
        assert rejected_state.values["approval_status"] == "rejected"
