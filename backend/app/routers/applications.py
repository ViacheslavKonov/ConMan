from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.audit import audit
from app.db import get_db
from app.dependencies import CsrfDep, require_roles
from app.models.core import Booking, BookingParticipant, Vendor
from app.models.user import User, UserRole
from app.schemas.step3 import RejectAction, ReviewAction
from app.services.planning import ensure_preference
from app.services.core import (
    booking_dict,
    booking_with_details,
    current_event_id,
    transition_booking,
)


router = APIRouter(prefix="/applications", tags=["applications"])

READ_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.VIEWER.value,
]
WRITE_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
]


def read_user():
    return require_roles(*READ_ROLES)


def write_user():
    return require_roles(*WRITE_ROLES)


@router.get("")
def application_inbox(
    filter: str = Query(default="PENDING"),
    q: str | None = Query(default=None, max_length=200),
    event_id: UUID | None = None,
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    event_id = event_id or current_event_id(db)

    if not event_id:
        return {
            "summary": {
                "pending": 0,
                "approved": 0,
                "confirmed": 0,
                "rejected": 0,
            },
            "items": [],
        }

    normalized = filter.upper()

    if normalized == "PENDING":
        statuses = ["SUBMITTED"]
    elif normalized == "APPROVED":
        statuses = ["APPROVED", "AWAITING_PAYMENT"]
    elif normalized == "CONFIRMED":
        statuses = ["CONFIRMED"]
    elif normalized == "REJECTED":
        statuses = ["REJECTED"]
    elif normalized == "ALL":
        statuses = [
            "SUBMITTED",
            "APPROVED",
            "AWAITING_PAYMENT",
            "CONFIRMED",
            "REJECTED",
        ]
    else:
        raise HTTPException(status_code=422, detail="Unknown application filter")

    stmt = (
        select(Booking)
        .join(Vendor, Vendor.id == Booking.vendor_id)
        .where(
            Booking.event_id == event_id,
            Booking.booking_status.in_(statuses),
        )
        .options(
            selectinload(Booking.vendor),
            selectinload(Booking.tariff),
            selectinload(Booking.participant_links)
            .selectinload(BookingParticipant.participant),
            selectinload(Booking.charges),
            selectinload(Booking.payments),
        )
        .order_by(Booking.application_date.desc())
    )

    if q and q.strip():
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Vendor.vendor_name.ilike(pattern),
                Vendor.email.ilike(pattern),
                Vendor.telegram.ilike(pattern),
                Booking.code.ilike(pattern),
            )
        )

    items = db.scalars(stmt.limit(500)).unique().all()

    counts = dict(
        db.execute(
            select(
                Booking.booking_status,
                func.count(Booking.id),
            )
            .where(Booking.event_id == event_id)
            .group_by(Booking.booking_status)
        ).all()
    )

    result = []
    for booking in items:
        data = booking_dict(booking, include_details=True)
        owner = next(
            (
                item
                for item in data.get("participants", [])
                if item["role"] == "OWNER"
            ),
            None,
        )

        data["owner"] = owner
        result.append(data)

    return {
        "summary": {
            "pending": int(counts.get("SUBMITTED", 0)),
            "approved": int(counts.get("APPROVED", 0))
            + int(counts.get("AWAITING_PAYMENT", 0)),
            "confirmed": int(counts.get("CONFIRMED", 0)),
            "rejected": int(counts.get("REJECTED", 0)),
        },
        "items": result,
    }


@router.post("/{booking_id}/approve")
def approve_application(
    booking_id: UUID,
    payload: ReviewAction,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    return review_transition(
        db,
        user,
        booking_id,
        "APPROVED",
        payload.comment,
    )


@router.post("/{booking_id}/reject")
def reject_application(
    booking_id: UUID,
    payload: RejectAction,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    return review_transition(
        db,
        user,
        booking_id,
        "REJECTED",
        payload.reason,
    )


@router.post("/{booking_id}/awaiting-payment")
def awaiting_payment(
    booking_id: UUID,
    payload: ReviewAction,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    return review_transition(
        db,
        user,
        booking_id,
        "AWAITING_PAYMENT",
        payload.comment,
    )


@router.post("/{booking_id}/confirm")
def confirm_application(
    booking_id: UUID,
    payload: ReviewAction,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    return review_transition(
        db,
        user,
        booking_id,
        "CONFIRMED",
        payload.comment,
    )


def review_transition(
    db: Session,
    user: User,
    booking_id: UUID,
    target: str,
    comment: str | None,
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    before = booking_dict(booking)

    transition_booking(
        db,
        booking,
        target,
        actor_id=user.id,
        comment=comment,
    )

    if target == "APPROVED":
        ensure_preference(db, booking)

    audit(
        db,
        user_id=user.id,
        entity_type="BOOKING",
        entity_id=str(booking.id),
        action="UPDATE",
        before=before,
        after=booking_dict(booking),
        metadata={
            "review_action": target,
        },
    )

    db.commit()

    loaded = booking_with_details(db, booking.id)
    return booking_dict(loaded, include_details=True)
