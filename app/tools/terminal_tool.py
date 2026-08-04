import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from app.config import ROOT_DIR
from app.security.command_guard import validate_command


def run_terminal_command(command: str, args: list[str], timeout_seconds: int = 30) -> dict[str, Any]:
    validate_command(command, args, ROOT_DIR)
    executable = sys.executable if command == "pytest" else command
    final_args = (["-m", "pytest"] + args) if command == "pytest" else args
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [executable, *final_args],
            cwd=ROOT_DIR,
            shell=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(max(timeout_seconds, 1), 120),
            env=None,
        )
        return {
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-12_000:],
            "stderr": completed.stderr[-12_000:],
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": -1,
            "stdout": (exc.stdout or "")[-12_000:] if isinstance(exc.stdout, str) else "",
            "stderr": "command timed out",
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "timed_out": True,
        }


def run_pytest(
    test_path: str = "tests/scenarios",
    keyword: str | None = None,
    marker: str | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    args = [test_path, "-v" if verbose else "-q"]
    if keyword:
        args.extend(["-k", keyword])
    if marker:
        if marker != "demo_failure":
            raise ValueError("only the controlled demo_failure marker may be selected")
        args.extend(["-m", marker, "-o", "addopts="])
    result = run_terminal_command("pytest", args, timeout_seconds=60)
    combined = f"{result['stdout']}\n{result['stderr']}"
    counts = {name: 0 for name in ("passed", "failed", "skipped", "errors")}
    for number, name in re.findall(r"(\d+)\s+(passed|failed|skipped|error)s?", combined):
        counts["errors" if name == "error" else name] = int(number)
    result.update(
        {
            "total_count": sum(counts.values()),
            "passed_count": counts["passed"],
            "failed_count": counts["failed"] + counts["errors"],
            "skipped_count": counts["skipped"],
            "possible_module": test_path if result["exit_code"] else None,
            "suggestion": "检查失败堆栈与对应接口文档。" if result["exit_code"] else "测试通过，无需修复。",
        }
    )
    return result
