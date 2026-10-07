import hmac
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.db import get_db
from app.models.session import AuthSession
from app.models.user import User
from app.security import hash_token

settings = get_settings()
DbDep = Annotated[Session, Depends(get_db)]


def get_current_session(
    db: DbDep,
    session_token: Annotated[
        str | None,
        Cookie(alias=settings.session_cookie_name),
    ] = None,
) -> AuthSession:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    auth_session = db.scalar(
        select(AuthSession)
        .options(joinedload(AuthSession.user))
        .where(AuthSession.token_hash == hash_token(session_token))
    )

    if (
        auth_session is None
        or auth_session.expires_at <= datetime.now(UTC)
        or auth_session.user is None
        or not auth_session.user.active
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    auth_session.last_seen_at = datetime.now(UTC)
    return auth_session


SessionDep = Annotated[AuthSession, Depends(get_current_session)]


def get_current_user(auth_session: SessionDep) -> User:
    return auth_session.user


UserDep = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    def dependency(user: UserDep) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


def require_csrf(
    auth_session: SessionDep,
    csrf_cookie: Annotated[
        str | None,
        Cookie(alias=settings.csrf_cookie_name),
    ] = None,
    csrf_header: Annotated[
        str | None,
        Header(alias="X-CSRF-Token"),
    ] = None,
) -> None:
    if not csrf_cookie or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing CSRF token",
        )

    if not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )

    if not hmac.compare_digest(
        hash_token(csrf_header),
        auth_session.csrf_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


CsrfDep = Annotated[None, Depends(require_csrf)]
