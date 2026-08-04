import pytest


def authenticate(username: str, password: str) -> dict[str, str]:
    if username == "alice" and password == "correct-password":
        return {"status": "ok", "user_id": "1"}
    return {"status": "error", "error_code": "AUTH001"}


def test_login_success() -> None:
    assert authenticate("alice", "correct-password")["status"] == "ok"


def test_login_invalid_credentials() -> None:
    assert authenticate("alice", "wrong-password")["error_code"] == "AUTH001"


@pytest.mark.demo_failure
def test_demo_auth_migration_regression() -> None:
    """Controlled failure: simulate a stale password-hash migration expectation."""
    result = authenticate("alice", "correct-password")
    assert result.get("error_code") == "AUTH001", "模拟失败：有效凭据不应被认证服务错误映射为 AUTH001"

