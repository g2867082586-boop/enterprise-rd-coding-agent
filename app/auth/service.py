import hashlib
import secrets
import uuid
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.password import hash_password, verify_password
from app.auth.schemas import RegisterRequest
from app.config import get_settings
from app.database.models import AppUser, UserSession
from app.infrastructure.redis_client import distributed_rate_limit


class DuplicateAccountError(ValueError):
    pass


_auth_rate_lock = threading.Lock()
_auth_attempts: dict[str, deque[float]] = defaultdict(deque)


def check_auth_rate_limit(key: str) -> None:
    now = time.monotonic()
    limit = get_settings().auth_rate_limit_per_minute
    distributed = distributed_rate_limit(f"auth:{key}", limit)
    if distributed is False:
        raise ValueError("请求过于频繁，请稍后再试")
    if distributed is True:
        return
    with _auth_rate_lock:
        attempts = _auth_attempts[key]
        while attempts and now - attempts[0] >= 60:
            attempts.popleft()
        if len(attempts) >= limit:
            raise ValueError("请求过于频繁，请稍后再试")
        attempts.append(now)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_user(db: Session, payload: RegisterRequest) -> AppUser:
    existing = db.scalar(
        select(AppUser).where(
            or_(AppUser.username == payload.username.lower(), AppUser.email == payload.email.lower())
        )
    )
    if existing:
        raise DuplicateAccountError("用户名或邮箱已被使用")
    now = utcnow()
    user = AppUser(
        id=str(uuid.uuid4()),
        username=payload.username.lower(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role="user",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, identifier: str, password: str) -> AppUser | None:
    normalized = identifier.strip().lower()
    user = db.scalar(
        select(AppUser).where(or_(AppUser.username == normalized, AppUser.email == normalized))
    )
    if not user or not verify_password(user.password_hash, password) or not user.is_active:
        return None
    user.last_login_at = utcnow()
    user.updated_at = user.last_login_at
    db.commit()
    return user


def create_user_session(db: Session, user: AppUser) -> tuple[UserSession, str]:
    now = utcnow()
    token = secrets.token_urlsafe(32)
    record = UserSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        session_token_hash=hash_session_token(token),
        expires_at=now + timedelta(hours=get_settings().session_ttl_hours),
        created_at=now,
        last_used_at=now,
        revoked_at=None,
    )
    db.add(record)
    db.commit()
    return record, token


def revoke_session(db: Session, token: str | None) -> None:
    if not token:
        return
    record = db.scalar(
        select(UserSession).where(UserSession.session_token_hash == hash_session_token(token))
    )
    if record and record.revoked_at is None:
        record.revoked_at = utcnow()
        db.commit()
