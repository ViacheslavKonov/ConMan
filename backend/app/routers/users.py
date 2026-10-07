from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.dependencies import CsrfDep, require_roles
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


def to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        active=user.active,
    )


@router.get("", response_model=list[UserResponse])
def list_users(
    current_user: User = Depends(require_roles(UserRole.ADMIN.value)),
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    users = db.scalars(
        select(User).order_by(User.display_name, User.email)
    ).all()
    return [to_response(user) for user in users]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    payload: UserCreate,
    _: CsrfDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN.value)),
    db: Session = Depends(get_db),
) -> UserResponse:
    existing = db.scalar(
        select(User).where(
            func.lower(User.email) == payload.email.lower()
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        active=payload.active,
    )
    db.add(user)
    db.flush()

    audit(
        db,
        user_id=current_user.id,
        entity_type="USER",
        entity_id=str(user.id),
        action="CREATE",
        after={
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "active": user.active,
        },
    )

    db.commit()
    db.refresh(user)
    return to_response(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    _: CsrfDep,
    current_user: User = Depends(require_roles(UserRole.ADMIN.value)),
    db: Session = Depends(get_db),
) -> UserResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    before = {
        "display_name": user.display_name,
        "role": user.role,
        "active": user.active,
    }

    next_role = payload.role if payload.role is not None else user.role
    next_active = payload.active if payload.active is not None else user.active

    if user.id == current_user.id and payload.active is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You cannot deactivate your own account",
        )

    was_active_admin = user.role == UserRole.ADMIN.value and user.active
    remains_active_admin = (
        next_role == UserRole.ADMIN.value and next_active
    )

    if was_active_admin and not remains_active_admin:
        other_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.id != user.id,
                User.role == UserRole.ADMIN.value,
                User.active.is_(True),
            )
        )
        if not other_admins:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last active ADMIN",
            )

    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.role is not None:
        user.role = payload.role
    if payload.active is not None:
        user.active = payload.active
    if payload.password:
        user.password_hash = hash_password(payload.password)

    after = {
        "display_name": user.display_name,
        "role": user.role,
        "active": user.active,
    }

    audit(
        db,
        user_id=current_user.id,
        entity_type="USER",
        entity_id=str(user.id),
        action="UPDATE",
        before=before,
        after=after,
        metadata={"password_changed": payload.password is not None},
    )

    db.commit()
    db.refresh(user)
    return to_response(user)
