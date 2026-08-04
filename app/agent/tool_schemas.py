from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NaturalLanguageQueryArgs(ToolArgs):
    question: str = Field(min_length=2, max_length=2000)


class KnowledgeSearchArgs(ToolArgs):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)
    allowed_scopes: list[str] = Field(default_factory=list, max_length=5)
    corpus_type: str = "mock"


class DescribeTableArgs(ToolArgs):
    table_name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class ReadonlySqlArgs(ToolArgs):
    sql: str = Field(min_length=6, max_length=5000)
    parameters: dict[str, Any] | None = None


class PytestArgs(ToolArgs):
    test_path: str = Field(default="tests/scenarios", max_length=300)
    keyword: str | None = Field(default=None, max_length=100)
    marker: str | None = Field(default=None, max_length=100)
    verbose: bool = False


class BrowserArgs(ToolArgs):
    url: str
    expected_text: str | None = Field(default=None, max_length=500)
    selector: str | None = Field(default=None, max_length=300)
    request_id: str | None = Field(default=None, max_length=100)


class SearchOrdersArgs(ToolArgs):
    order_no: str | None = Field(default=None, pattern=r"^NS\d{8}$")
    user_id: int | None = Field(default=None, ge=1)
    status: str | None = Field(default=None, pattern=r"^(PROCESSING|PAID|FAILED|CANCELLED)$")
    error_code: str | None = Field(default=None, max_length=32)
    created_from: str | None = None
    created_to: str | None = None
    min_amount: float | None = Field(default=None, ge=0)
    max_amount: float | None = Field(default=None, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: str = Field(default="created_at_desc")


class GetOrderArgs(ToolArgs):
    order_no: str = Field(pattern=r"^NS\d{8}$")


class OrderStatisticsArgs(ToolArgs):
    created_from: str | None = None
    created_to: str | None = None


class PrepareOrderActionArgs(ToolArgs):
    action_type: str = Field(
        pattern=r"^(create_order|update_order_status|cancel_order|add_order_note)$"
    )
    parameters: dict[str, Any]
    request_user_id: str = Field(min_length=1, max_length=36)
    session_id: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=100)


SCHEMAS: dict[str, type[ToolArgs]] = {
    "natural_language_query": NaturalLanguageQueryArgs,
    "search_knowledge_base": KnowledgeSearchArgs,
    "describe_table": DescribeTableArgs,
    "execute_readonly_sql": ReadonlySqlArgs,
    "run_pytest": PytestArgs,
    "browser_check": BrowserArgs,
    "search_orders": SearchOrdersArgs,
    "get_order": GetOrderArgs,
    "get_order_statistics": OrderStatisticsArgs,
    "prepare_order_action": PrepareOrderActionArgs,
}


def validate_tool_arguments(action: str, arguments: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(arguments)
    if action == "natural_language_query" and "question" not in normalized and "query" in normalized:
        normalized["question"] = normalized.pop("query")
    schema = SCHEMAS.get(action)
    if schema is None:
        raise ValueError(f"unsupported tool action: {action}")
    return schema.model_validate(normalized).model_dump(exclude_none=True)
