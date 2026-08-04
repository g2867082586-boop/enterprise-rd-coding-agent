from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


RouteType = Literal[
    "direct_answer", "knowledge_base", "database", "order_mutation",
    "test", "browser", "hybrid", "clarify"
]
ActionType = Literal[
    "search_knowledge_base", "describe_table", "execute_readonly_sql", "natural_language_query",
    "search_orders", "get_order", "get_order_statistics", "prepare_order_action",
    "run_pytest", "browser_check", "ask_clarification", "generate_answer",
]
ToolType = Literal[
    "search_knowledge_base", "describe_table", "execute_readonly_sql",
    "natural_language_query", "search_orders", "get_order", "get_order_statistics",
    "prepare_order_action", "run_pytest", "browser_check",
]


class RouteDecision(BaseModel):
    route: RouteType
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=2, max_length=500)
    rewritten_query: str = Field(min_length=1, max_length=2000)
    required_tools: list[ToolType] = Field(default_factory=list, max_length=8)
    extracted_parameters: dict[str, Any] = Field(default_factory=dict)
    needs_planning: bool = False


class PlanStep(BaseModel):
    step_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,32}$")
    action: ActionType
    objective: str = Field(min_length=2, max_length=300)
    depends_on: list[str] = Field(default_factory=list, max_length=6)
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False


class ExecutionPlan(BaseModel):
    goal: str = Field(min_length=2, max_length=1000)
    steps: list[PlanStep] = Field(min_length=1, max_length=8)
    max_steps: int = Field(ge=1, le=8)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "ExecutionPlan":
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("plan step_id values must be unique")
        known: set[str] = set()
        for step in self.steps:
            if not set(step.depends_on).issubset(known):
                raise ValueError("plan dependencies must reference earlier steps")
            known.add(step.step_id)
        return self
