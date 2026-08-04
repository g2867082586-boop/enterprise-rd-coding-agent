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
