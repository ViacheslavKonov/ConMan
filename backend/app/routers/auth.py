from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.dependencies import CsrfDep, SessionDep, UserDep
from app.models.session import AuthSession
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest
from app.security import cleanup_expired_sessions, create_session, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


@router.post("/login", response_model=CurrentUserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CurrentUserResponse:
    cleanup_expired_sessions(db)

    user = db.scalar(
        select(User).where(
            func.lower(User.email) == payload.email.lower()
        )
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
