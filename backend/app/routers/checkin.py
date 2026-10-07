from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit import audit
from app.db import get_db
from app.dependencies import CsrfDep, require_roles
from app.models.core import Booking, BookingParticipant
from app.models.user import User, UserRole
from app.schemas.checkin import BadgeIssueInput, CheckInActionInput
from app.services.checkin import (
    cancel_check_in,
    checkin_overview,
    do_check_in,
    get_link_for_action,
    issue_badge,
)
from app.services.core import current_event_id


router = APIRouter(prefix="/checkin", tags=["checkin"])

CHECKIN_VIEW_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.REGISTRATION.value,
    UserRole.VIEWER.value,
]
CHECKIN_ACTION_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.REGISTRATION.value,
]


def view_user():
    return require_roles(*CHECKIN_VIEW_ROLES)


def action_user():
    return require_roles(*CHECKIN_ACTION_ROLES)


@router.get("")
def list_checkin(
    q: str | None = Query(default=None, max_length=200),
    filter: str = Query(default="EXPECTED"),
    event_id: UUID | None = None,
    _: User = Depends(view_user()),
    db: Session = Depends(get_db),
):
    return checkin_overview(
        db,
        event_id,
        q,
        filter,
    )


@router.post("/{link_id}/check-in")
def check_in_participant(
    link_id: UUID,
    payload: CheckInActionInput,
    _: CsrfDep,
    user: User = Depends(action_user()),
    db: Session = Depends(get_db),
):
    link = get_link_for_action(db, link_id)
    changed = do_check_in(
        db,
        link,
        user,
        payload.notes,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="CHECKIN",
        entity_id=str(link.id),
        action="CHECK_IN",
        after={
            "booking_id": str(link.booking_id),
            "participant_id": str(link.participant_id),
            "changed": changed,
        },
    )

    db.commit()
    return {
        "changed": changed,
        "item": checkin_overview(
            db,
            link.booking.event_id,
            link.participant.code,
            "ALL",
        )["items"][0],
    }


@router.post("/{link_id}/cancel")
def cancel_participant_checkin(
    link_id: UUID,
    payload: CheckInActionInput,
    _: CsrfDep,
    user: User = Depends(action_user()),
    db: Session = Depends(get_db),
):
    link = get_link_for_action(db, link_id)
    changed = cancel_check_in(
        db,
        link,
        user,
        payload.notes,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="CHECKIN",
        entity_id=str(link.id),
        action="CHECK_IN_CANCELLED",
        after={
            "booking_id": str(link.booking_id),
            "participant_id": str(link.participant_id),
            "changed": changed,
        },
    )

    db.commit()
    return {"changed": changed}


@router.post("/{link_id}/badge")
def issue_participant_badge(
    link_id: UUID,
    payload: BadgeIssueInput,
    _: CsrfDep,
    user: User = Depends(action_user()),
    db: Session = Depends(get_db),
):
    link = get_link_for_action(db, link_id)
    action = issue_badge(
        db,
        link,
        user,
        payload.badge_number,
        payload.notes,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="CHECKIN",
        entity_id=str(link.id),
        action=action,
        after={
            "booking_id": str(link.booking_id),
            "participant_id": str(link.participant_id),
            "badge_number": link.badge_number,
        },
    )

    db.commit()
    return {
        "action": action,
        "badge_issued": link.badge_issued,
        "badge_number": link.badge_number,
    }


@router.post("/bookings/{booking_id}/team")
def check_in_booking_team(
    booking_id: UUID,
    payload: CheckInActionInput,
    _: CsrfDep,
    user: User = Depends(action_user()),
    db: Session = Depends(get_db),
):
    event_id = current_event_id(db)

    booking = db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(
                Booking.participant_links
            ).selectinload(
                BookingParticipant.participant
            )
        )
    )
    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    changed = 0
    for link in booking.participant_links:
        if (
            link.registration_status
            == "CANCELLED"
        ):
            continue
        if do_check_in(
            db,
            link,
            user,
            payload.notes,
        ):
            changed += 1

    audit(
        db,
        user_id=user.id,
        entity_type="CHECKIN",
        entity_id=str(booking.id),
        action="TEAM_CHECK_IN",
        after={
            "booking_id": str(booking.id),
            "changed": changed,
        },
    )

    db.commit()
    return {
        "changed": changed,
        "booking_id": str(booking.id),
        "event_id": str(
            event_id or booking.event_id
        ),
    }
