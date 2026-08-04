import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.auth.service import utcnow
from app.database.connection import get_engine, get_order_engine
from app.database.models import AgentAction
from app.infrastructure.redis_client import publish_event
from app.orders.schemas import (
    AddOrderNotePayload,
    CancelOrderPayload,
    CreateOrderPayload,
    OrderSearchParams,
    UpdateStatusPayload,
)


ALLOWED_TRANSITIONS = {
    "PROCESSING": {"PAID", "FAILED", "CANCELLED"},
    "FAILED": {"PROCESSING", "CANCELLED"},
    "PAID": set(),
    "CANCELLED": set(),
}


class OrderConflictError(ValueError):
    pass


def _serialize(row: Any) -> dict[str, Any]:
    result = dict(row._mapping if hasattr(row, "_mapping") else row)
    for key, value in result.items():
        if isinstance(value, Decimal):
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
    if "email" in result:
        result["email"] = "***"
    return result


def search_orders(params: OrderSearchParams) -> dict[str, Any]:
    clauses: list[str] = []
    values: dict[str, Any] = {}
    for field in ("order_no", "user_id", "status", "error_code"):
        value = getattr(params, field)
        if value is not None:
            clauses.append(f"o.{field} = :{field}")
            values[field] = value
    mappings = (
        ("created_from", "o.created_at >= :created_from"),
        ("created_to", "o.created_at <= :created_to"),
        ("min_amount", "o.amount >= :min_amount"),
        ("max_amount", "o.amount <= :max_amount"),
    )
    for field, clause in mappings:
        value = getattr(params, field)
        if value is not None:
            clauses.append(clause)
            values[field] = value
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    ordering = {
        "created_at_desc": "o.created_at DESC",
        "created_at_asc": "o.created_at ASC",
        "amount_desc": "o.amount DESC",
        "amount_asc": "o.amount ASC",
    }[params.sort]
    values.update({"limit": params.page_size, "offset": (params.page - 1) * params.page_size})
    with get_engine().connect() as connection:
        total = int(connection.scalar(text(f"SELECT COUNT(*) FROM orders o{where}"), values) or 0)
        rows = connection.execute(
            text(
                "SELECT o.order_no, o.user_id, o.amount, o.status, o.error_code, "
                "o.created_at, o.updated_at, COALESCE(o.version, 1) AS version "
                f"FROM orders o{where} ORDER BY {ordering} LIMIT :limit OFFSET :offset"
            ),
            values,
        ).fetchall()
    return {
        "items": [_serialize(row) for row in rows],
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": (total + params.page_size - 1) // params.page_size,
    }


def get_order(order_no: str) -> dict[str, Any] | None:
    with get_engine().connect() as connection:
        row = connection.execute(
            text(
                "SELECT order_no, user_id, amount, status, error_code, created_at, updated_at, "
                "COALESCE(version, 1) AS version, note, cancel_reason FROM orders "
                "WHERE order_no=:order_no"
            ),
            {"order_no": order_no},
        ).first()
    return _serialize(row) if row else None


def order_statistics(created_from: Any = None, created_to: Any = None) -> dict[str, Any]:
    clauses, values = [], {}
    if created_from:
        clauses.append("created_at >= :created_from")
        values["created_from"] = created_from
    if created_to:
        clauses.append("created_at <= :created_to")
        values["created_to"] = created_to
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_engine().connect() as connection:
        status_rows = connection.execute(
            text(f"SELECT status, COUNT(*) AS count FROM orders{where} GROUP BY status"), values
        ).fetchall()
        error_where = f"{where} {'AND' if where else 'WHERE'} status='FAILED'"
        error_rows = connection.execute(
            text(
                f"SELECT error_code, COUNT(*) AS count FROM orders{error_where} "
                "GROUP BY error_code ORDER BY count DESC"
            ),
            values,
        ).fetchall()
    return {
        "by_status": [_serialize(row) for row in status_rows],
        "by_error_code": [_serialize(row) for row in error_rows],
    }


def _current_for_update(connection: Connection, order_no: str) -> dict[str, Any]:
    suffix = " FOR UPDATE" if connection.dialect.name == "mysql" else ""
    row = connection.execute(
        text(f"SELECT * FROM orders WHERE order_no=:order_no{suffix}"), {"order_no": order_no}
    ).mappings().first()
    if not row:
        raise ValueError("订单不存在")
    return _serialize(row)


def _audit(
    connection: Connection,
    order_no: str,
    action_type: str,
    actor_user_id: str,
    before: dict[str, Any],
    after: dict[str, Any],
    request_id: str | None,
) -> None:
    now, event_id = utcnow(), str(uuid.uuid4())
    connection.execute(
        text(
            "INSERT INTO order_audit_logs "
            "(id,order_no,action_type,actor_user_id,before_json,after_json,request_id,created_at) "
            "VALUES (:id,:order_no,:action_type,:actor,:before_json,:after_json,:request_id,:created_at)"
        ),
        {
            "id": str(uuid.uuid4()), "order_no": order_no, "action_type": action_type,
            "actor": actor_user_id, "before_json": json.dumps(before, ensure_ascii=False, default=str),
            "after_json": json.dumps(after, ensure_ascii=False, default=str),
            "request_id": request_id, "created_at": now,
        },
    )
    payload = {"order_no": order_no, "action": action_type, "version": after.get("version")}
    connection.execute(
        text(
            "INSERT INTO outbox_events "
            "(id,aggregate_type,aggregate_id,event_type,payload_json,created_at,published_at) "
            "VALUES (:id,'order',:order_no,:event_type,:payload,:created_at,NULL)"
        ),
        {
            "id": event_id, "order_no": order_no, "event_type": f"order.{action_type}",
            "payload": json.dumps(payload, ensure_ascii=False), "created_at": now,
        },
    )
    publish_event("order-events", {"event_id": event_id, **payload})


def create_order(payload: CreateOrderPayload, actor_user_id: str, request_id: str | None = None) -> dict[str, Any]:
    now = utcnow()
    order_no = f"NS{uuid.uuid4().int % 100_000_000:08d}"
    engine = get_order_engine()
    with engine.begin() as connection:
        if not connection.scalar(text("SELECT COUNT(*) FROM users WHERE id=:id"), {"id": payload.user_id}):
            raise ValueError("业务用户不存在")
        next_id = int(connection.scalar(text("SELECT COALESCE(MAX(id),0)+1 FROM orders")) or 1)
        connection.execute(
            text(
                "INSERT INTO orders "
                "(id,user_id,order_no,amount,status,error_code,created_at,updated_at,version,note,created_by,updated_by) "
                "VALUES (:id,:user_id,:order_no,:amount,'PROCESSING',NULL,:now,:now,1,:note,:actor,:actor)"
            ),
            {
                "id": next_id, "user_id": payload.user_id, "order_no": order_no,
                "amount": payload.amount, "now": now, "note": payload.note, "actor": actor_user_id,
            },
        )
        after = _current_for_update(connection, order_no)
        _audit(connection, order_no, "created", actor_user_id, {}, after, request_id)
    return after


def update_order_status(
    payload: UpdateStatusPayload, actor_user_id: str, request_id: str | None = None
) -> dict[str, Any]:
    with get_order_engine().begin() as connection:
        before = _current_for_update(connection, payload.order_no)
        if int(before.get("version", 1)) != payload.expected_version:
            raise OrderConflictError("订单已被其他操作更新，请刷新后重试")
        if payload.target_status not in ALLOWED_TRANSITIONS.get(str(before["status"]), set()):
            raise ValueError(f"不允许从 {before['status']} 变更为 {payload.target_status}")
        connection.execute(
            text(
                "UPDATE orders SET status=:status,error_code=:error_code,updated_at=:updated_at,"
                "updated_by=:actor,version=version+1 WHERE order_no=:order_no AND version=:version"
            ),
            {
                "status": payload.target_status, "error_code": payload.error_code,
                "updated_at": utcnow(), "actor": actor_user_id, "order_no": payload.order_no,
                "version": payload.expected_version,
            },
        )
        after = _current_for_update(connection, payload.order_no)
        _audit(connection, payload.order_no, "status_updated", actor_user_id, before, after, request_id)
    return after


def cancel_order(
    payload: CancelOrderPayload, actor_user_id: str, request_id: str | None = None
) -> dict[str, Any]:
    with get_order_engine().begin() as connection:
        before = _current_for_update(connection, payload.order_no)
        if int(before.get("version", 1)) != payload.expected_version:
            raise OrderConflictError("订单已被其他操作更新，请刷新后重试")
        if "CANCELLED" not in ALLOWED_TRANSITIONS.get(str(before["status"]), set()):
            raise ValueError(f"状态 {before['status']} 的订单不能取消")
        connection.execute(
            text(
                "UPDATE orders SET status='CANCELLED',cancel_reason=:reason,updated_at=:updated_at,"
                "updated_by=:actor,version=version+1 WHERE order_no=:order_no AND version=:version"
            ),
            {
                "reason": payload.reason, "updated_at": utcnow(), "actor": actor_user_id,
                "order_no": payload.order_no, "version": payload.expected_version,
            },
        )
        after = _current_for_update(connection, payload.order_no)
        _audit(connection, payload.order_no, "cancelled", actor_user_id, before, after, request_id)
    return after


def add_order_note(
    payload: AddOrderNotePayload, actor_user_id: str, request_id: str | None = None
) -> dict[str, Any]:
    with get_order_engine().begin() as connection:
        before = _current_for_update(connection, payload.order_no)
        if int(before.get("version", 1)) != payload.expected_version:
            raise OrderConflictError("订单已被其他操作更新，请刷新后重试")
        connection.execute(
            text(
                "UPDATE orders SET note=:note,updated_at=:updated_at,updated_by=:actor,"
                "version=version+1 WHERE order_no=:order_no AND version=:version"
            ),
            {
                "note": payload.note, "updated_at": utcnow(), "actor": actor_user_id,
                "order_no": payload.order_no, "version": payload.expected_version,
            },
        )
        after = _current_for_update(connection, payload.order_no)
        _audit(connection, payload.order_no, "note_added", actor_user_id, before, after, request_id)
    return after


def prepare_action(
    db: Session,
    request_user_id: str,
    session_id: str | None,
    action_type: str,
    parameters: dict[str, object],
    idempotency_key: str,
) -> AgentAction:
    normalized = json.dumps(parameters, ensure_ascii=False, sort_keys=True, default=str)
    existing = db.query(AgentAction).filter(AgentAction.idempotency_key == idempotency_key).first()
    if existing:
        if existing.parameter_hash != hashlib.sha256(normalized.encode()).hexdigest():
            raise OrderConflictError("幂等键已用于不同操作")
        return existing
    schemas = {
        "create_order": CreateOrderPayload,
        "update_order_status": UpdateStatusPayload,
        "cancel_order": CancelOrderPayload,
        "add_order_note": AddOrderNotePayload,
    }
    schema = schemas.get(action_type)
    if not schema:
        raise ValueError("不支持的订单操作")
    validated = schema.model_validate(parameters).model_dump(mode="json")
    normalized = json.dumps(validated, ensure_ascii=False, sort_keys=True)
    risk = "high" if action_type == "cancel_order" else "medium"
    row = AgentAction(
        id=str(uuid.uuid4()), request_user_id=request_user_id, session_id=session_id,
        action_type=action_type, risk_level=risk,
        status="pending_admin" if risk == "high" else "pending_confirmation",
        parameters_json=normalized, parameter_hash=hashlib.sha256(normalized.encode()).hexdigest(),
        idempotency_key=idempotency_key, result_json="{}", created_at=utcnow(),
        expires_at=utcnow() + timedelta(hours=1),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def execute_action(db: Session, action: AgentAction, actor_user_id: str) -> dict[str, Any]:
    if action.status == "completed":
        return json.loads(action.result_json)
    if action.expires_at <= utcnow():
        action.status = "expired"
        db.commit()
        raise OrderConflictError("操作已过期")
    functions = {
        "create_order": (CreateOrderPayload, create_order),
        "update_order_status": (UpdateStatusPayload, update_order_status),
        "cancel_order": (CancelOrderPayload, cancel_order),
        "add_order_note": (AddOrderNotePayload, add_order_note),
    }
    schema, function = functions[action.action_type]
    payload = schema.model_validate(json.loads(action.parameters_json))
    result = function(payload, actor_user_id, action.id)
    action.status = "completed"
    action.approved_by = actor_user_id
    action.completed_at = utcnow()
    action.result_json = json.dumps(result, ensure_ascii=False, default=str)
    db.commit()
    return result
