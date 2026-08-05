"""Isolated repository tools used by the Coding Agent foundation."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR


WORKSPACE_ROOT = ROOT_DIR / "data" / "coding_workspaces"
WORKSPACE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}$")
SKIPPED_DIRS = {".git", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".toml", ".yaml", ".yml",
    ".md", ".txt", ".html", ".css", ".sql", ".ini", ".cfg",
}


class CodeWorkspaceError(ValueError):
    pass


def _run_git(args: list[str], cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, shell=False, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )


def _workspace(workspace_id: str | None, *, must_exist: bool = True) -> Path:
    if not workspace_id:
        return ROOT_DIR
    if not WORKSPACE_ID.fullmatch(workspace_id):
        raise CodeWorkspaceError("invalid workspace_id")
    path = (WORKSPACE_ROOT / workspace_id).resolve()
    path.relative_to(WORKSPACE_ROOT.resolve())
    if must_exist and not path.is_dir():
        raise CodeWorkspaceError("coding workspace does not exist")
    return path


def _safe_path(root: Path, relative_path: str, *, require_file: bool = False) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        raise CodeWorkspaceError("absolute paths are forbidden")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CodeWorkspaceError("path escapes coding workspace") from exc
    if require_file and not resolved.is_file():
        raise CodeWorkspaceError("file does not exist")
    return resolved


def create_code_workspace(workspace_id: str) -> dict[str, Any]:
    """Create a detached Git worktree so model edits never touch the main checkout."""
    destination = _workspace(workspace_id, must_exist=False)
    if destination.exists():
        raise CodeWorkspaceError("coding workspace already exists")
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    result = _run_git(["worktree", "add", "--detach", str(destination), "HEAD"], ROOT_DIR, 60)
    if result.returncode:
        raise CodeWorkspaceError(result.stderr[-1000:] or "failed to create Git worktree")
    return {"workspace_id": workspace_id, "status": "ready", "head": _run_git(["rev-parse", "HEAD"], destination).stdout.strip()}


def discard_code_workspace(workspace_id: str) -> dict[str, Any]:
    """Remove only the generated detached worktree identified by workspace_id."""
    destination = _workspace(workspace_id)
    if destination == ROOT_DIR:
        raise CodeWorkspaceError("the main checkout cannot be removed")
    result = _run_git(["worktree", "remove", "--force", str(destination)], ROOT_DIR, 60)
    _run_git(["worktree", "prune"], ROOT_DIR)
    if result.returncode:
        raise CodeWorkspaceError(result.stderr[-1000:] or "failed to discard Git worktree")
    return {"workspace_id": workspace_id, "status": "discarded"}


def list_repository(workspace_id: str | None = None, relative_path: str = ".", max_entries: int = 200) -> list[str]:
    root = _workspace(workspace_id)
    base = _safe_path(root, relative_path)
    if not base.exists():
        raise CodeWorkspaceError("path does not exist")
    entries: list[str] = []
    candidates = [base] if base.is_file() else base.rglob("*")
    for path in candidates:
        if any(part in SKIPPED_DIRS for part in path.relative_to(root).parts) or not path.is_file():
            continue
        entries.append(path.relative_to(root).as_posix())
        if len(entries) >= max(1, min(max_entries, 500)):
            break
    return sorted(entries)


def search_code(
    query: str, workspace_id: str | None = None, relative_path: str = ".", max_results: int = 50,
) -> list[dict[str, Any]]:
    if not query or len(query) > 300:
        raise CodeWorkspaceError("query length must be between 1 and 300")
    root = _workspace(workspace_id)
    results: list[dict[str, Any]] = []
    for name in list_repository(workspace_id, relative_path, max_entries=500):
        path = root / name
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 1_000_000:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            if query.casefold() in line.casefold():
                results.append({"path": name, "line": number, "text": line.strip()[:500]})
                if len(results) >= max(1, min(max_results, 100)):
                    return results
    return results


def read_code_file(
    path: str, workspace_id: str | None = None, start_line: int = 1, end_line: int = 200,
) -> dict[str, Any]:
    root = _workspace(workspace_id)
    resolved = _safe_path(root, path, require_file=True)
    if resolved.stat().st_size > 1_000_000:
        raise CodeWorkspaceError("file is too large")
    lines = resolved.read_text(encoding="utf-8").splitlines()
    start = max(1, start_line)
    end = min(len(lines), max(start, min(end_line, start + 399)))
    return {"path": resolved.relative_to(root).as_posix(), "start_line": start, "end_line": end,
            "content": "\n".join(f"{index}: {lines[index - 1]}" for index in range(start, end + 1))}


def _validate_patch_paths(patch_text: str, root: Path) -> None:
    if not patch_text or len(patch_text.encode("utf-8")) > 100_000:
        raise CodeWorkspaceError("patch must be non-empty and at most 100 KB")
    if "GIT binary patch" in patch_text or "Binary files" in patch_text:
        raise CodeWorkspaceError("binary patches are forbidden")
    paths = []
    for line in patch_text.splitlines():
        if line.startswith(("--- ", "+++ ")):
            value = line[4:].split("\t", 1)[0]
            if value != "/dev/null":
                paths.append(value[2:] if value.startswith(("a/", "b/")) else value)
    if not paths:
        raise CodeWorkspaceError("patch does not contain file paths")
    for value in paths:
        _safe_path(root, value)


def apply_code_patch(workspace_id: str, patch_text: str) -> dict[str, Any]:
    """Apply a unified diff only inside an isolated detached worktree."""
    root = _workspace(workspace_id)
    if root == ROOT_DIR:
        raise CodeWorkspaceError("patches require an isolated workspace_id")
    _validate_patch_paths(patch_text, root)
    check = subprocess.run(
        ["git", "apply", "--check", "--recount", "--whitespace=nowarn", "-"],
        cwd=root, input=patch_text, shell=False,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    if check.returncode:
        return {"applied": False, "error": check.stderr[-2000:]}
    applied = subprocess.run(
        ["git", "apply", "--recount", "--whitespace=nowarn", "-"],
        cwd=root, input=patch_text, shell=False,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return {"applied": applied.returncode == 0, "error": applied.stderr[-2000:] or None,
            "diff": git_diff(workspace_id)["diff"]}


def git_diff(workspace_id: str) -> dict[str, Any]:
    root = _workspace(workspace_id)
    # Intent-to-add makes new text files visible in `git diff` without staging contents.
    intent = _run_git(["add", "-N", "--", "."], root)
    if intent.returncode:
        return {"exit_code": intent.returncode, "diff": "", "error": intent.stderr[-2000:]}
    result = _run_git(["diff", "--no-ext-diff", "--unified=3"], root)
    return {"exit_code": result.returncode, "diff": result.stdout[-50_000:], "error": result.stderr[-2000:] or None}


def run_code_checks(workspace_id: str, test_path: str = "tests/unit", timeout_seconds: int = 90) -> dict[str, Any]:
    root = _workspace(workspace_id)
    target = _safe_path(root, test_path)
    if not target.exists() or "tests" not in target.relative_to(root).parts:
        raise CodeWorkspaceError("test_path must point inside the workspace tests directory")
    started = __import__("time").perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", target.relative_to(root).as_posix(), "-q"],
            cwd=root, shell=False, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=min(max(timeout_seconds, 1), 120),
        )
        return {"exit_code": result.returncode, "passed": result.returncode == 0,
                "stdout": result.stdout[-12_000:], "stderr": result.stderr[-12_000:],
                "duration_ms": round((__import__("time").perf_counter() - started) * 1000)}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "passed": False, "stdout": "", "stderr": "checks timed out",
                "duration_ms": round((__import__("time").perf_counter() - started) * 1000)}
