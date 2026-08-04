import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user
from app.auth.schemas import LoginRequest, RegisterRequest, UpdateProfileRequest, UserResponse
from app.auth.service import (
    DuplicateAccountError,
    authenticate_user,
    check_auth_rate_limit,
    create_user_session,
    register_user,
    revoke_session,
    utcnow,
)
from app.config import get_settings
from app.database.models import AppUser
from app.database.session import get_db
from app.security.csrf import CSRF_COOKIE


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=secrets.token_urlsafe(24),
        max_age=settings.session_ttl_hours * 3600,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> AppUser:
    try:
        check_auth_rate_limit(f"register:{request.client.host if request.client else 'unknown'}")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    try:
        return register_user(db, payload)
    except DuplicateAccountError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> AppUser:
    try:
        check_auth_rate_limit(f"login:{request.client.host if request.client else 'unknown'}")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    _, token = create_user_session(db, user)
    _set_session_cookie(response, token)
    return user


@router.get("/me", response_model=UserResponse)
def me(user: AppUser = Depends(current_user)) -> AppUser:
    return user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UpdateProfileRequest,
    user: AppUser = Depends(current_user),
    db: Session = Depends(get_db),
) -> AppUser:
    user.display_name = payload.display_name
    user.updated_at = utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    settings = get_settings()
    revoke_session(db, request.cookies.get(settings.session_cookie_name))
    result = Response(status_code=status.HTTP_204_NO_CONTENT)
    result.delete_cookie(settings.session_cookie_name, path="/", samesite="lax")
    result.delete_cookie(CSRF_COOKIE, path="/", samesite="lax")
    return result
