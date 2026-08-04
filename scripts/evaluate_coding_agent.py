"""Evaluate Coding Agent tasks with deterministic test and diff checks."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.coding.agent import run_coding_task
from app.config import ROOT_DIR
from app.llm.provider import get_llm
from app.tools.codebase_tool import discard_code_workspace


async def evaluate(dataset_path: Path, keep_workspaces: bool = False) -> dict:
    provider = get_llm()
    if provider.mode == "mock":
        raise RuntimeError("Coding Agent evaluation requires a configured real LLM")
    tasks = json.loads(dataset_path.read_text(encoding="utf-8"))
    samples = []
    for row in tasks:
        workspace_id = f"eval-{row['id']}-{uuid4().hex[:8]}"
        try:
            result = await run_coding_task(
                row["issue"], workspace_id, max_attempts=int(row.get("max_attempts", 2))
            )
            diff = result.get("diff", "")
            expected_paths = row.get("expected_paths", [])
            path_check = all(path in diff for path in expected_paths)
            passed = result.get("status") == "passed" and path_check
            samples.append({
                "id": row["id"],
                "passed": passed,
                "tests_passed": result.get("status") == "passed",
                "expected_paths_present": path_check,
                "attempt_count": len(result.get("attempts", [])),
                "workspace_id": workspace_id if keep_workspaces else None,
                "attempts": result.get("attempts", []),
            })
        except Exception as exc:
            samples.append({"id": row["id"], "passed": False, "error": str(exc)[:1000]})
        finally:
            if not keep_workspaces:
                try:
                    discard_code_workspace(workspace_id)
                except Exception:
                    pass
    passed = sum(int(row["passed"]) for row in samples)
    attempts = [row.get("attempt_count", 0) for row in samples]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider": provider.mode,
        "total": len(samples),
        "passed": passed,
        "task_pass_rate": passed / len(samples) if samples else 0,
        "average_attempts": sum(attempts) / len(attempts) if attempts else 0,
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate isolated Coding Agent tasks")
    parser.add_argument(
        "--dataset", type=Path,
        default=ROOT_DIR / "tests" / "evaluation" / "coding_tasks.json",
    )
    parser.add_argument(
        "--output", type=Path,
        default=ROOT_DIR / "artifacts" / "evaluation" / "coding-agent-report.json",
    )
    parser.add_argument("--keep-workspaces", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(evaluate(args.dataset, args.keep_workspaces))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
