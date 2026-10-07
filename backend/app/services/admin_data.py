from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.core import (
    AppSetting,
    Booking,
    BookingParticipant,
    Charge,
    Event,
    LayoutTable,
    LayoutZone,
    Participant,
    Payment,
    TableAssignment,
    Tariff,
    Vendor,
)
from app.services.core import (
    booking_dict,
    current_event_id,
    event_dict,
    participant_dict,
    recalculate_booking,
    tariff_dict,
    vendor_dict,
)
from app.services.seating import (
    assignment_dict,
    table_dict,
    zone_dict,
)


def management_state(
    db: Session,
    event_id: UUID | None,
) -> dict:
    event_id = event_id or current_event_id(db)

    events = db.scalars(
        select(Event).order_by(
            Event.start_date.desc(),
            Event.event_name,
        )
    ).all()

    if not event_id:
        return {
            "current_event_id": None,
            "events": [event_dict(item) for item in events],
            "tariffs": [],
            "vendors": [],
            "bookings": [],
            "participants": [],
            "zones": [],
            "tables": [],
            "assignments": [],
        }

    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    tariffs = db.scalars(
        select(Tariff)
        .where(Tariff.event_id == event_id)
        .order_by(
            Tariff.booking_type,
            Tariff.valid_from.desc(),
        )
    ).all()

    bookings = db.scalars(
        select(Booking)
        .where(Booking.event_id == event_id)
        .options(
            selectinload(Booking.vendor),
            selectinload(Booking.tariff),
            selectinload(
                Booking.participant_links
            ).selectinload(
                BookingParticipant.participant
            ),
            selectinload(Booking.charges),
            selectinload(Booking.payments),
            selectinload(
                Booking.table_assignment
            ).selectinload(
                TableAssignment.table
            ),
        )
        .order_by(Booking.code)
    ).all()

    vendors = db.scalars(
        select(Vendor).order_by(Vendor.vendor_name)
    ).all()

    participant_rows = []
    for booking in bookings:
        for link in booking.participant_links:
            participant_rows.append(
                {
                    "link_id": str(link.id),
                    "booking_id": str(booking.id),
                    "booking_code": booking.code,
                    "vendor_name": (
                        booking.vendor.vendor_name
                        if booking.vendor
                        else ""
                    ),
                    "role": link.role,
                    "registration_status": (
                        link.registration_status
                    ),
                    "checkin_status": (
                        link.checkin_status
                    ),
                    "participant": participant_dict(
                        link.participant
                    ),
                }
            )

    zones = db.scalars(
        select(LayoutZone)
        .where(LayoutZone.event_id == event_id)
        .order_by(
            LayoutZone.sort_order,
            LayoutZone.zone_name,
        )
    ).all()

    tables = db.scalars(
        select(LayoutTable)
        .where(LayoutTable.event_id == event_id)
        .order_by(LayoutTable.table_number)
    ).all()

    assignments = db.scalars(
        select(TableAssignment)
        .where(
            TableAssignment.event_id == event_id,
            TableAssignment.active.is_(True),
        )
        .options(
            selectinload(
                TableAssignment.booking
            ).selectinload(Booking.vendor),
            selectinload(
                TableAssignment.booking
            ).selectinload(Booking.tariff),
            selectinload(
                TableAssignment.booking
            ).selectinload(
                Booking.participant_links
            ).selectinload(
                BookingParticipant.participant
            ),
            selectinload(
                TableAssignment.booking
            ).selectinload(Booking.charges),
            selectinload(
                TableAssignment.booking
            ).selectinload(Booking.payments),
            selectinload(TableAssignment.table),
        )
    ).all()

    return {
        "current_event_id": str(
            current_event_id(db)
        ) if current_event_id(db) else None,
        "event": event_dict(event),
        "events": [event_dict(item) for item in events],
        "tariffs": [
            tariff_dict(item) for item in tariffs
        ],
        "vendors": [
            vendor_dict(item)
            for item in vendors
        ],
        "bookings": [
            booking_dict(
                item,
                include_details=True,
            )
            for item in bookings
        ],
        "participants": participant_rows,
        "zones": [
            zone_dict(item) for item in zones
        ],
        "tables": [
            table_dict(item) for item in tables
        ],
        "assignments": [
            assignment_dict(item)
            for item in assignments
        ],
    }


def cleanup_orphan_participants(
    db: Session,
    participant_ids: set[UUID],
) -> int:
    deleted = 0
    for participant_id in participant_ids:
        still_used = db.scalar(
            select(func.count())
            .select_from(BookingParticipant)
            .where(
                BookingParticipant.participant_id
                == participant_id
            )
        )
        if still_used:
            continue

        participant = db.get(
            Participant,
            participant_id,
        )
        if participant:
            db.delete(participant)
            deleted += 1

    db.flush()
    return deleted


def delete_booking_cascade(
    db: Session,
    booking: Booking,
) -> dict:
    participant_ids = {
        link.participant_id
        for link in booking.participant_links
    }

    summary = {
        "booking": booking.code,
        "participants_links": len(
            booking.participant_links
        ),
        "charges": len(booking.charges),
        "payments": len(booking.payments),
        "assignment": bool(
            booking.table_assignment
        ),
    }

    db.delete(booking)
    db.flush()

    summary["orphan_participants_deleted"] = (
        cleanup_orphan_participants(
            db,
            participant_ids,
        )
    )
    return summary


def load_booking_for_delete(
    db: Session,
    booking_id: UUID,
) -> Booking:
    booking = db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(
                Booking.participant_links
            ),
            selectinload(Booking.charges),
            selectinload(Booking.payments),
            selectinload(
                Booking.table_assignment
            ),
        )
    )
    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )
    return booking


def clear_or_replace_current_event(
    db: Session,
    deleted_event_id: UUID,
) -> str | None:
    if current_event_id(db) != deleted_event_id:
        current = current_event_id(db)
        return str(current) if current else None

    replacement = db.scalar(
        select(Event)
        .where(Event.id != deleted_event_id)
        .order_by(
            Event.start_date.desc(),
            Event.created_at.desc(),
        )
        .limit(1)
    )

    setting = db.get(
        AppSetting,
        "current_event_id",
    )
    if setting is None:
        setting = AppSetting(
            key="current_event_id",
            value=None,
        )
        db.add(setting)

    setting.value = (
        str(replacement.id)
        if replacement
        else None
    )
    db.flush()
    return setting.value


def apply_booking_admin_update(
    db: Session,
    booking: Booking,
    vendor_id: UUID | None,
    tariff_id: UUID | None,
    notes_set: bool,
    notes: str | None,
    actor_id: UUID,
) -> Booking:
    if vendor_id and vendor_id != booking.vendor_id:
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            raise HTTPException(
                status_code=404,
                detail="Vendor not found",
            )

        duplicate = db.scalar(
            select(Booking).where(
                Booking.id != booking.id,
                Booking.event_id
                == booking.event_id,
                Booking.vendor_id == vendor_id,
                Booking.booking_status.notin_(
                    ["CANCELLED", "REJECTED"]
                ),
            )
        )
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Target vendor already has "
                    f"active booking {duplicate.code}"
                ),
            )

        booking.vendor_id = vendor_id

    if tariff_id and tariff_id != booking.tariff_id:
        tariff = db.get(Tariff, tariff_id)
        if not tariff:
            raise HTTPException(
                status_code=404,
                detail="Tariff not found",
            )
        if tariff.event_id != booking.event_id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Tariff belongs to another event"
                ),
            )

        booking.tariff_id = tariff.id
        booking.booking_type = (
            tariff.booking_type
        )
        booking.base_price = tariff.base_price
        booking.included_helpers = (
            tariff.included_helpers
        )
        booking.extra_participant_price = (
            tariff.extra_participant_price
        )

    if notes_set:
        booking.notes = notes

    booking.updated_by = actor_id
    recalculate_booking(
        db,
        booking,
        actor_id,
    )
    return booking


def cancel_payment_record(
    db: Session,
    payment: Payment,
    actor_id: UUID,
) -> Booking:
    if payment.status == "CANCELLED":
        return db.get(
            Booking,
            payment.booking_id,
        )

    payment.status = "CANCELLED"
    payment.updated_at = func.now()

    booking = db.get(
        Booking,
        payment.booking_id,
    )
    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    recalculate_booking(
        db,
        booking,
        actor_id,
    )
    return booking


def deactivate_manual_charge(
    db: Session,
    charge: Charge,
    actor_id: UUID,
) -> Booking:
    if charge.automatic:
        raise HTTPException(
            status_code=409,
            detail=(
                "Automatic charges are controlled "
                "by the pricing engine"
            ),
        )

    charge.active = False

    booking = db.get(
        Booking,
        charge.booking_id,
    )
    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    recalculate_booking(
        db,
        booking,
        actor_id,
    )
    return booking
