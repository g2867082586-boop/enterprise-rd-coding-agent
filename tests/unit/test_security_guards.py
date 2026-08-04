from pathlib import Path

import pytest

from app.security.command_guard import UnsafeCommandError, validate_command
from app.security.url_guard import UnsafeUrlError, validate_url


def test_command_guard_accepts_structured_pytest() -> None:
    assert validate_command("pytest", ["tests/unit", "-q"], Path.cwd())[0] == "pytest"


@pytest.mark.parametrize("command,args", [("powershell", []), ("pytest", ["tests && whoami"]), ("python", ["x.py", ">", "out"])])
def test_command_guard_rejects_shell_escape(command: str, args: list[str]) -> None:
    with pytest.raises(UnsafeCommandError):
        validate_command(command, args, Path.cwd())


@pytest.mark.parametrize(
    "command,args",
    [
        ("pytest", ["../../outside.py"]),
        ("pytest", ["-p", "malicious_plugin"]),
        ("pytest", ["--basetemp", "../outside"]),
        ("ruff", ["check", "--fix", "app"]),
    ],
)
def test_command_guard_rejects_workspace_escape_and_unsafe_options(
    command: str, args: list[str]
) -> None:
    with pytest.raises(UnsafeCommandError):
        validate_command(command, args, Path.cwd())


def test_url_guard_allows_loopback_only() -> None:
    assert validate_url("http://127.0.0.1:8000/", {"127.0.0.1"}).startswith("http")
    with pytest.raises(UnsafeUrlError):
        validate_url("https://example.com", {"localhost", "127.0.0.1"})
