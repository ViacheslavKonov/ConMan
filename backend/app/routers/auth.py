from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import get_settings
from app.db import get_db
from app.dependencies import CsrfDep, SessionDep, UserDep
from app.models.core import AppSetting
from app.models.session import AuthSession
from app.models.user import User, UserRole
from app.schemas.auth import (
    BootstrapRequest,
    BootstrapStatus,
    CurrentUserResponse,
    LoginRequest,
)
from app.security import (
    cleanup_expired_sessions,
    create_session,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
BOOTSTRAP_COMPLETED_KEY = "admin_bootstrap_completed"


def user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


def bootstrap_required(db: Session) -> bool:
    # Any existing account closes public setup, even an inactive non-admin.
    return (
        db.get(AppSetting, BOOTSTRAP_COMPLETED_KEY) is None
        and db.scalar(select(User.id).limit(1)) is None
    )


@router.get("/bootstrap", response_model=BootstrapStatus)
def bootstrap_status(
    response: Response,
    db: Session = Depends(get_db),
) -> BootstrapStatus:
    response.headers["Cache-Control"] = "no-store"
    return BootstrapStatus(required=bootstrap_required(db))


def sign_in(
    db: Session,
    user: User,
    request: Request,
    response: Response,
) -> CurrentUserResponse:
    _, session_token, csrf_token = create_session(
        db,
        user,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    db.commit()

    cookie_kwargs = {
        "path": "/",
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "domain": settings.cookie_domain or None,
    }

    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        max_age=settings.session_ttl_hours * 3600,
        **cookie_kwargs,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        max_age=settings.session_ttl_hours * 3600,
        **cookie_kwargs,
    )

    return user_response(user)


@router.post("/bootstrap", response_model=CurrentUserResponse, status_code=201)
def bootstrap_admin(
    payload: BootstrapRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    # Serialize setup across workers and also block concurrent CLI/user inserts.
    # The lock is released when sign_in commits or the session rolls back.
    db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    if not bootstrap_required(db):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Первоначальная настройка уже завершена. Войдите в систему.",
        )

    user = User(
        email=str(payload.email).lower(),
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN.value,
        active=True,
    )
    db.add(user)
    db.flush()
    # Retain completion even if all users are later removed outside the app.
    db.add(AppSetting(key=BOOTSTRAP_COMPLETED_KEY, value="true"))
    audit(
        db,
        user_id=user.id,
        entity_type="USER",
        entity_id=str(user.id),
        action="CREATE",
        after={
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "active": user.active,
        },
        metadata={"source": "INITIAL_SETUP"},
    )
    return sign_in(db, user, request, response)


@router.post("/login", response_model=CurrentUserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    cleanup_expired_sessions(db)
    user = db.scalar(
        select(User).where(func.lower(User.email) == payload.email.lower())
    )
    if (
        user is None
        or not user.active
        or not verify_password(payload.password, user.password_hash)
    ):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return sign_in(db, user, request, response)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    auth_session: SessionDep,
    _: CsrfDep,
    db: Session = Depends(get_db),
) -> Response:
    db.execute(
        delete(AuthSession).where(AuthSession.id == auth_session.id)
    )
    db.commit()

    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        domain=settings.cookie_domain or None,
    )
    response.delete_cookie(
        settings.csrf_cookie_name,
        path="/",
        domain=settings.cookie_domain or None,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=CurrentUserResponse)
def me(user: UserDep) -> CurrentUserResponse:
    return user_response(user)
