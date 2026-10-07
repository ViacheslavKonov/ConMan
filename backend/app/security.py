import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.session import AuthSession
from app.models.user import User

_password_hasher = PasswordHasher()
settings = get_settings()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def create_session(
    db: Session,
    user: User,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[AuthSession, str, str]:
    session_token = new_opaque_token()
    csrf_token = new_opaque_token()
    now = datetime.now(UTC)

    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(session_token),
        csrf_hash=hash_token(csrf_token),
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        last_seen_at=now,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:500] or None,
    )
    db.add(auth_session)
    db.flush()

    return auth_session, session_token, csrf_token


def cleanup_expired_sessions(db: Session) -> None:
    db.execute(
        delete(AuthSession).where(
            AuthSession.expires_at <= datetime.now(UTC)
        )
    )
