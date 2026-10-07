from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.core import (
    Booking,
    BookingParticipant,
    CheckInLog,
    Event,
    Participant,
    TableAssignment,
    Vendor,
)
from app.models.user import User
from app.services.codes import next_code
from app.services.core import current_event_id


def require_checkin_open(
    db: Session,
    event_id: UUID,
    user: User,
) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.vendor_checkin_open or user.role == "ADMIN":
        return event

    raise HTTPException(
        status_code=409,
        detail="Check-in is closed for operators",
    )


def refresh_booking_checkin_status(
    db: Session,
    booking: Booking,
) -> None:
    links = db.scalars(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == booking.id,
            BookingParticipant.registration_status != "CANCELLED",
        )
    ).all()

    total = len(links)
    arrived = sum(
        1
        for link in links
        if link.checkin_status == "CHECKED_IN"
    )

    if total == 0 or arrived == 0:
        booking.checkin_status = "NONE"
    elif arrived < total:
        booking.checkin_status = "PARTIAL"
    else:
        booking.checkin_status = "COMPLETE"

    db.flush()


def add_checkin_log(
    db: Session,
    link: BookingParticipant,
    action: str,
    user_id: UUID | None,
    notes: str | None = None,
) -> CheckInLog:
    booking = link.booking
    row = CheckInLog(
        code=next_code(db, "CHK"),
        event_id=booking.event_id,
        booking_id=booking.id,
        participant_id=link.participant_id,
        booking_participant_id=link.id,
        action=action,
        user_id=user_id,
        notes=notes,
    )
    db.add(row)
    db.flush()
    return row


def participant_row(
    link: BookingParticipant,
) -> dict:
    booking = link.booking
    participant = link.participant
    vendor = booking.vendor if booking else None
    assignment = booking.table_assignment if booking else None
    table = assignment.table if assignment else None

    table_label = None
    if table and assignment:
        table_label = table.table_label
        if (
            assignment.slot_count == 1
            and table.capacity_slots > 1
        ):
            table_label += (
                "A"
                if assignment.start_slot == 1
                else "B"
            )

    return {
        "booking_participant_id": str(link.id),
        "booking_id": str(booking.id),
        "booking_code": booking.code,
        "booking_type": booking.booking_type,
        "booking_status": booking.booking_status,
        "booking_checkin_status": booking.checkin_status,
        "participant_id": str(participant.id),
        "participant_code": participant.code,
        "last_name": participant.last_name,
        "first_name": participant.first_name,
        "middle_name": participant.middle_name,
        "nickname": participant.nickname,
        "role": link.role,
        "vendor_id": str(vendor.id) if vendor else None,
        "vendor_name": vendor.vendor_name if vendor else "",
        "table_label": table_label,
        "checkin_status": link.checkin_status,
        "checkin_time": link.checkin_time,
        "badge_required": link.badge_required,
        "badge_issued": link.badge_issued,
        "badge_number": link.badge_number,
        "final_total": booking.final_total,
        "paid_amount": booking.paid_amount,
        "balance": booking.balance,
        "payment_status": booking.payment_status,
    }


def load_event_links(
    db: Session,
    event_id: UUID,
) -> list[BookingParticipant]:
    return list(
        db.scalars(
            select(BookingParticipant)
            .join(
                Booking,
                Booking.id
                == BookingParticipant.booking_id,
            )
            .where(
                Booking.event_id == event_id,
                BookingParticipant.registration_status
                != "CANCELLED",
                Booking.booking_status.notin_(
                    ["CANCELLED", "REJECTED"]
                ),
            )
            .options(
                selectinload(
                    BookingParticipant.participant
                ),
                selectinload(
                    BookingParticipant.booking
                ).selectinload(Booking.vendor),
                selectinload(
                    BookingParticipant.booking
                )
                .selectinload(
                    Booking.table_assignment
                )
                .selectinload(
                    TableAssignment.table
                ),
            )
            .order_by(
                Booking.code,
                BookingParticipant.sort_order,
            )
        ).all()
    )


def checkin_overview(
    db: Session,
    event_id: UUID | None,
    query: str | None,
    filter_name: str,
) -> dict:
    event_id = event_id or current_event_id(db)
    if not event_id:
        return {
            "event": None,
            "summary": {
                "expected": 0,
                "arrived": 0,
                "badges": 0,
                "bookings_complete": 0,
            },
            "items": [],
        }

    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    links = load_event_links(db, event_id)
    rows = [participant_row(link) for link in links]

    normalized_filter = filter_name.upper()
    if normalized_filter == "EXPECTED":
        rows = [
            row
            for row in rows
            if row["checkin_status"]
            != "CHECKED_IN"
        ]
    elif normalized_filter == "ARRIVED":
        rows = [
            row
            for row in rows
            if row["checkin_status"]
            == "CHECKED_IN"
        ]
    elif normalized_filter != "ALL":
        raise HTTPException(
            status_code=422,
            detail="Unknown check-in filter",
        )

    if query and query.strip():
        needle = query.strip().lower()

        def searchable(row: dict) -> str:
            return " ".join(
                str(value or "")
                for value in [
                    row["last_name"],
                    row["first_name"],
                    row["middle_name"],
                    row["nickname"],
                    row["vendor_name"],
                    row["table_label"],
                    row["booking_code"],
                    row["participant_code"],
                ]
            ).lower()

        rows = [
            row
            for row in rows
            if needle in searchable(row)
        ]

    total_expected = len(links)
    total_arrived = sum(
        1
        for link in links
        if link.checkin_status == "CHECKED_IN"
    )
    total_badges = sum(
        1 for link in links if link.badge_issued
    )

    booking_ids = {
        link.booking_id for link in links
    }
    complete_booking_ids = {
        link.booking_id
        for link in links
        if link.booking.checkin_status == "COMPLETE"
    }

    return {
        "event": {
            "id": str(event.id),
            "event_name": event.event_name,
            "vendor_checkin_open": event.vendor_checkin_open,
        },
        "summary": {
            "expected": total_expected,
            "arrived": total_arrived,
            "badges": total_badges,
            "bookings_complete": len(
                complete_booking_ids
                & booking_ids
            ),
        },
        "items": rows,
    }


def get_link_for_action(
    db: Session,
    link_id: UUID,
) -> BookingParticipant:
    link = db.scalar(
        select(BookingParticipant)
        .where(
            BookingParticipant.id == link_id
        )
        .options(
            selectinload(
                BookingParticipant.participant
            ),
            selectinload(
                BookingParticipant.booking
            ).selectinload(Booking.vendor),
            selectinload(
                BookingParticipant.booking
            )
            .selectinload(
                Booking.table_assignment
            )
            .selectinload(
                TableAssignment.table
            ),
        )
    )
    if not link:
        raise HTTPException(
            status_code=404,
            detail="Participant link not found",
        )
    return link


def do_check_in(
    db: Session,
    link: BookingParticipant,
    user: User,
    notes: str | None,
) -> bool:
    require_checkin_open(
        db,
        link.booking.event_id,
        user,
    )

    if link.checkin_status == "CHECKED_IN":
        return False

    now = datetime.now(UTC)
    link.checkin_status = "CHECKED_IN"
    link.checkin_time = now
    link.checkin_user_id = user.id
    link.updated_by = user.id

    add_checkin_log(
        db,
        link,
        "CHECK_IN",
        user.id,
        notes,
    )
    refresh_booking_checkin_status(
        db,
        link.booking,
    )
    return True


def cancel_check_in(
    db: Session,
    link: BookingParticipant,
    user: User,
    notes: str | None,
) -> bool:
    require_checkin_open(
        db,
        link.booking.event_id,
        user,
    )

    if link.checkin_status != "CHECKED_IN":
        return False

    link.checkin_status = "NOT_CHECKED_IN"
    link.checkin_time = None
    link.checkin_user_id = None
    link.updated_by = user.id

    add_checkin_log(
        db,
        link,
        "CHECK_IN_CANCELLED",
        user.id,
        notes,
    )
    refresh_booking_checkin_status(
        db,
        link.booking,
    )
    return True


def issue_badge(
    db: Session,
    link: BookingParticipant,
    user: User,
    badge_number: str | None,
    notes: str | None,
) -> str:
    require_checkin_open(
        db,
        link.booking.event_id,
        user,
    )

    if link.checkin_status != "CHECKED_IN":
        raise HTTPException(
            status_code=409,
            detail="Participant must be checked in before badge issue",
        )

    action = (
        "BADGE_REPLACED"
        if link.badge_issued
        else "BADGE_ISSUED"
    )

    link.badge_issued = True
    if badge_number is not None:
        link.badge_number = (
            badge_number.strip() or None
        )
    link.updated_by = user.id

    add_checkin_log(
        db,
        link,
        action,
        user.id,
        notes,
    )
    db.flush()
    return action
