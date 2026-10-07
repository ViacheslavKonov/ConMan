from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_roles
from app.models.user import User, UserRole
from app.services.reports import build_report


router = APIRouter(
    prefix="/reports",
    tags=["reports"],
)


def read_user():
    return require_roles(
        UserRole.ADMIN.value,
        UserRole.MANAGER.value,
        UserRole.REGISTRATION.value,
        UserRole.VIEWER.value,
    )


@router.get("/{report_name}")
def get_report(
    report_name: str,
    event_id: UUID | None = None,
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    return build_report(
        db,
        report_name,
        event_id,
    )
