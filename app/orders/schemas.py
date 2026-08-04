from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


OrderStatus = Literal["PROCESSING", "PAID", "FAILED", "CANCELLED"]


class OrderSearchParams(BaseModel):
    order_no: str | None = Field(default=None, pattern=r"^NS\d{8}$")
    user_id: int | None = Field(default=None, ge=1)
    status: OrderStatus | None = None
    error_code: str | None = Field(default=None, max_length=32)
    created_from: datetime | None = None
    created_to: datetime | None = None
    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: Literal["created_at_desc", "created_at_asc", "amount_desc", "amount_asc"] = "created_at_desc"

    @model_validator(mode="after")
    def validate_ranges(self) -> "OrderSearchParams":
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from must be before created_to")
        if self.min_amount is not None and self.max_amount is not None and self.min_amount > self.max_amount:
            raise ValueError("min_amount must not exceed max_amount")
        return self


class CreateOrderPayload(BaseModel):
    user_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    note: str | None = Field(default=None, max_length=1000)


class UpdateStatusPayload(BaseModel):
    order_no: str = Field(pattern=r"^NS\d{8}$")
    target_status: OrderStatus
    expected_version: int = Field(ge=1)
    error_code: str | None = Field(default=None, max_length=32)


class CancelOrderPayload(BaseModel):
    order_no: str = Field(pattern=r"^NS\d{8}$")
    reason: str = Field(min_length=2, max_length=500)
    expected_version: int = Field(ge=1)


class AddOrderNotePayload(BaseModel):
    order_no: str = Field(pattern=r"^NS\d{8}$")
    note: str = Field(min_length=1, max_length=1000)
    expected_version: int = Field(ge=1)


class PrepareActionRequest(BaseModel):
    action_type: Literal["create_order", "update_order_status", "cancel_order", "add_order_note"]
    parameters: dict[str, object]
    idempotency_key: str = Field(min_length=8, max_length=100)
