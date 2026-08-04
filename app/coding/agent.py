"""Bounded edit-test-repair loop for isolated coding tasks."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.coding.schemas import CodePatchProposal
from app.llm.provider import get_llm
from app.tools.codebase_tool import (
    CodeWorkspaceError,
    apply_code_patch,
    create_code_workspace,
    git_diff,
    list_repository,
    read_code_file,
    run_code_checks,
    search_code,
)


ProposalFactory = Callable[[str, str, str], Awaitable[CodePatchProposal]]


def _search_terms(issue: str) -> list[str]:
    quoted = re.findall(r"[`'\"]([^`'\"]{2,80})[`'\"]", issue)
    identifiers = re.findall(r"\b[A-Za-z_][A-Za-z0-9_.]{2,80}\b", issue)
    return list(dict.fromkeys([*quoted, *identifiers]))[:8]


def build_code_context(issue: str, workspace_id: str, max_chars: int = 20_000) -> str:
    """Retrieve bounded source context without embedding secrets or generated files."""
    matches: list[dict[str, Any]] = []
    for term in _search_terms(issue):
        matches.extend(search_code(term, workspace_id, max_results=12))
    unique: dict[tuple[str, int], dict[str, Any]] = {
        (row["path"], row["line"]): row for row in matches
    }
    chunks: list[str] = []
    for row in list(unique.values())[:20]:
        start = max(1, int(row["line"]) - 12)
        end = int(row["line"]) + 20
        content = read_code_file(row["path"], workspace_id, start, end)
        chunks.append(f"FILE {row['path']}\n{content['content']}")
        if sum(len(chunk) for chunk in chunks) >= max_chars:
            break
    if not chunks:
        files = list_repository(workspace_id, max_entries=120)
        chunks.append("REPOSITORY FILES\n" + "\n".join(files))
    return "\n\n".join(chunks)[:max_chars]


async def _llm_proposal(issue: str, context: str, feedback: str) -> CodePatchProposal:
    provider = get_llm()
    if provider.mode == "mock":
        raise RuntimeError("Coding patch generation requires a configured real LLM")
    system = """You are a repository coding agent. Return CodePatchProposal JSON only.
Produce one minimal unified diff with paths relative to the repository root. Do not modify secrets,
dependencies, generated files, CI credentials, or files outside the repository. Include or update tests.
The patch will be applied in an isolated Git worktree and validated with pytest. test_path must stay
inside tests/. Use the failure feedback to produce an incremental patch for the current worktree."""
    payload = json.dumps(
        {"issue": issue, "repository_context": context, "previous_feedback": feedback},
        ensure_ascii=False,
    )
    return await provider.generate_structured(system, payload, CodePatchProposal)


async def run_coding_task(
    issue: str,
    workspace_id: str,
    max_attempts: int = 2,
    proposal_factory: ProposalFactory | None = None,
) -> dict[str, Any]:
    """Generate, apply and test patches with bounded retry feedback.

    The generated worktree is intentionally retained for human diff review. Call
    ``discard_code_workspace`` explicitly after accepting or rejecting the result.
    """
    if not issue.strip() or len(issue) > 4000:
        raise ValueError("issue length must be between 1 and 4000")
    if proposal_factory is None and get_llm().mode == "mock":
        raise RuntimeError("Coding patch generation requires a configured real LLM")
    try:
        create_code_workspace(workspace_id)
    except CodeWorkspaceError as exc:
        if "already exists" not in str(exc):
            raise
    context = build_code_context(issue, workspace_id)
    proposer = proposal_factory or _llm_proposal
    attempts: list[dict[str, Any]] = []
    feedback = ""
    for attempt in range(1, min(max(max_attempts, 1), 3) + 1):
        proposal = await proposer(issue, context, feedback)
        applied = apply_code_patch(workspace_id, proposal.patch_text)
        if not applied["applied"]:
            feedback = f"Patch apply failed:\n{applied.get('error') or 'unknown error'}"
            attempts.append({"attempt": attempt, "summary": proposal.summary,
                             "patch_applied": False, "checks_passed": False, "feedback": feedback})
            continue
        checks = run_code_checks(workspace_id, proposal.test_path)
        attempts.append({"attempt": attempt, "summary": proposal.summary, "patch_applied": True,
                         "checks_passed": checks["passed"], "test_path": proposal.test_path,
                         "duration_ms": checks["duration_ms"]})
        if checks["passed"]:
            return {"status": "passed", "workspace_id": workspace_id, "attempts": attempts,
                    "diff": git_diff(workspace_id)["diff"], "checks": checks}
        feedback = (
            "Tests failed. Produce an incremental patch against the current worktree.\n"
            + checks["stdout"][-6000:] + "\n" + checks["stderr"][-3000:]
        )
    return {"status": "failed", "workspace_id": workspace_id, "attempts": attempts,
            "diff": git_diff(workspace_id)["diff"], "feedback": feedback[-9000:]}
