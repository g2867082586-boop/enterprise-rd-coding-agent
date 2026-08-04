from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import hash_session_token, utcnow
from app.config import get_settings
from app.database.models import AppUser, UserSession
from app.database.session import get_db


def current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> AppUser:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录")
    now = utcnow()
    row = db.execute(
        select(UserSession, AppUser)
        .join(AppUser, AppUser.id == UserSession.user_id)
        .where(
            UserSession.session_token_hash == hash_session_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
            AppUser.is_active.is_(True),
        )
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录")
    session, user = row
    if (now - session.last_used_at).total_seconds() > 60:
        session.last_used_at = now
        db.commit()
    return user


def admin_user(user: AppUser = Depends(current_user)) -> AppUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
