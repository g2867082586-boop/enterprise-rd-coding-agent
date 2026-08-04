import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings


_lock = threading.Lock()
SENSITIVE_KEYS = {"password", "token", "api_key", "authorization", "cookie"}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("***" if key.lower() in SENSITIVE_KEYS else _sanitize(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    text = str(value)
    return text[:4000] if len(text) > 4000 else value


def record_trace(request_id: str, event: dict[str, Any]) -> dict[str, Any]:
    trace_dir = get_settings().project_path(get_settings().trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{request_id}.jsonl"
    with _lock:
        sequence = 1
        if path.exists():
            sequence = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) + 1
        payload = {
            "request_id": request_id,
            "sequence": sequence,
            "span_id": event.get("span_id") or f"span-{sequence:04d}",
            "parent_span_id": event.get("parent_span_id"),
            "event_type": event.get("event_type", "span"),
            "recorded_at": datetime.now(UTC).isoformat(),
            **_sanitize(event),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    return payload


def replace_trace_event(request_id: str, match: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    """Replace one matching trace event, preserving sequence and span identity."""
    trace_dir = get_settings().project_path(get_settings().trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{request_id}.jsonl"
    with _lock:
        rows = []
        if path.exists():
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        target_index = next(
            (
                index for index, row in enumerate(rows)
                if all(row.get(key) == value for key, value in match.items())
            ),
            None,
        )
        if target_index is None:
            sequence = len(rows) + 1
            payload = {
                "request_id": request_id,
                "sequence": sequence,
                "span_id": event.get("span_id") or f"span-{sequence:04d}",
                "parent_span_id": event.get("parent_span_id"),
                "event_type": event.get("event_type", "span"),
                "recorded_at": datetime.now(UTC).isoformat(),
                **_sanitize(event),
            }
            rows.append(payload)
            with path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            return payload
        original = rows[target_index]
        payload = {
            **original,
            **_sanitize(event),
            "request_id": request_id,
            "sequence": original.get("sequence", target_index + 1),
            "span_id": original.get("span_id") or event.get("span_id") or f"span-{target_index + 1:04d}",
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        rows[target_index] = payload
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        return payload


def append_trace_event(request_id: str, event: dict[str, Any]) -> dict[str, Any]:
    """Alias kept for callers that want explicit append semantics."""
    return record_trace(request_id, event)


def read_traces(request_id: str) -> list[dict[str, Any]]:
    safe = "".join(c for c in request_id if c.isalnum() or c in "-_")
    if safe != request_id:
        raise ValueError("invalid request_id")
    path = get_settings().project_path(get_settings().trace_dir) / f"{safe}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
