import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user
from app.config import get_settings
from app.database.connection import get_order_engine
from app.database.models import AgentAction, AppUser
from app.database.session import get_db
from app.orders.schemas import OrderSearchParams, PrepareActionRequest
from app.orders.service import (
    OrderConflictError,
    execute_action,
    get_order,
    order_statistics,
    prepare_action,
    search_orders,
)


router = APIRouter(prefix="/api", tags=["orders"])


def _write_role(user: AppUser) -> None:
    if user.role not in {"order_operator", "admin"}:
        raise HTTPException(403, "需要订单操作员或管理员权限")


@router.get("/orders")
def list_orders(
    order_no: str | None = None,
    user_id: int | None = None,
    status: str | None = None,
    error_code: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    min_amount: str | None = None,
    max_amount: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = "created_at_desc",
    _: AppUser = Depends(current_user),
) -> dict[str, object]:
    try:
        params = OrderSearchParams.model_validate(locals())
        return search_orders(params)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/orders/statistics")
def statistics(
    created_from: str | None = None,
    created_to: str | None = None,
    _: AppUser = Depends(current_user),
) -> dict[str, object]:
    return order_statistics(created_from, created_to)


@router.get("/orders/{order_no}")
def order_detail(order_no: str, _: AppUser = Depends(current_user)) -> dict[str, object]:
    result = get_order(order_no)
    if not result:
        raise HTTPException(404, "订单不存在")
    return result


@router.post("/order-actions", status_code=202)
def create_action(
    payload: PrepareActionRequest,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _write_role(user)
    try:
        row = prepare_action(
            db, user.id, None, payload.action_type, payload.parameters, payload.idempotency_key
        )
        return {
            "id": row.id, "action_type": row.action_type, "risk_level": row.risk_level,
            "status": row.status, "parameters": json.loads(row.parameters_json),
            "expires_at": row.expires_at,
        }
    except (ValueError, OrderConflictError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/order-actions/{action_id}/confirm")
def confirm_action(
    action_id: str,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    _write_role(user)
    action = db.get(AgentAction, action_id)
    if not action or (action.request_user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "操作不存在")
    if idempotency_key and idempotency_key != action.idempotency_key:
        raise HTTPException(409, "幂等键不匹配")
    if action.status == "pending_admin" and user.role != "admin":
        raise HTTPException(403, "该操作需要管理员批准")
    if action.status not in {"pending_confirmation", "pending_admin", "completed"}:
        raise HTTPException(409, f"当前状态 {action.status} 不可执行")
    try:
        return {"id": action.id, "status": "completed", "result": execute_action(db, action, user.id)}
    except (ValueError, OrderConflictError) as exc:
        raise HTTPException(409, str(exc)) from exc


async def _order_event_stream(after: str | None, user_id: str) -> AsyncIterator[str]:
    last_created = after
    last_updated: str | None = None
    while True:
        with get_order_engine().connect() as connection:
            params = {"after": last_created or "1970-01-01"}
            events = connection.execute(
                text(
                    "SELECT id,event_type,payload_json,created_at FROM outbox_events "
                    "WHERE aggregate_type='order' AND created_at>:after ORDER BY created_at LIMIT 100"
                ),
                params,
            ).mappings().all()
            maximum = connection.scalar(text("SELECT MAX(updated_at) FROM orders"))
        for event in events:
            last_created = str(event["created_at"])
            yield f"id: {event['id']}\nevent: order\ndata: {event['payload_json']}\n\n"
        current_updated = str(maximum) if maximum else None
        if last_updated is not None and current_updated != last_updated and not events:
            yield (
                "event: orders_changed\n"
                f"data: {json.dumps({'updated_at': current_updated, 'viewer': user_id})}\n\n"
            )
        last_updated = current_updated
        yield "event: heartbeat\ndata: {}\n\n"
        await asyncio.sleep(get_settings().order_event_poll_seconds)


@router.get("/orders/events/stream")
def order_events(
    after: str | None = None, user: AppUser = Depends(current_user)
) -> StreamingResponse:
    return StreamingResponse(
        _order_event_stream(after, user.id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
