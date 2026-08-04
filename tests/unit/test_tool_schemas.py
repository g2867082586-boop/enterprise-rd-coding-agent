import pytest
from pydantic import ValidationError

from app.agent.tool_schemas import validate_tool_arguments


def test_natural_language_query_accepts_safe_query_alias() -> None:
    assert validate_tool_arguments("natural_language_query", {"query": "最近七天失败订单"}) == {
        "question": "最近七天失败订单"
    }


def test_tool_arguments_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        validate_tool_arguments("natural_language_query", {"question": "查询订单", "dangerous": True})


def test_code_search_schema_is_bounded() -> None:
    assert validate_tool_arguments("search_code", {"query": "run_agent"})["max_results"] == 50
    with pytest.raises(ValidationError):
        validate_tool_arguments("search_code", {"query": "x", "relative_path": "../../outside" * 30})


def test_coding_task_requires_bounded_workspace_and_attempts() -> None:
    parsed = validate_tool_arguments(
        "run_coding_task", {"issue": "修复登录接口", "workspace_id": "task-login"}
    )
    assert parsed["max_attempts"] == 2
    with pytest.raises(ValidationError):
        validate_tool_arguments(
            "run_coding_task", {"issue": "修复", "workspace_id": "../escape", "max_attempts": 9}
        )
