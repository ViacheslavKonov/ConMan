from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.core import (
    Booking,
    BookingParticipant,
    Event,
    LayoutTable,
    LayoutZone,
    TableAssignment,
)
from app.services.core import current_event_id
from app.services.checkin import load_event_links, participant_row


REPORT_NAMES = {
    "vendors",
    "participants",
    "seating",
    "finance",
    "checkin",
}


def _assignment_label(
    assignment: TableAssignment | None,
) -> str:
    if not assignment or not assignment.table:
        return ""

    table = assignment.table
    label = table.table_label
    if (
        assignment.slot_count == 1
        and table.capacity_slots > 1
    ):
        label += (
            "A"
            if assignment.start_slot == 1
            else "B"
        )
    return label


def _event_id(
    db: Session,
    event_id: UUID | None,
) -> UUID:
    value = event_id or current_event_id(db)
    if not value:
        raise HTTPException(
            status_code=409,
            detail="Current event is not selected",
        )
    if not db.get(Event, value):
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )
    return value


def _bookings(
    db: Session,
    event_id: UUID,
) -> list[Booking]:
    return list(
        db.scalars(
            select(Booking)
            .where(
                Booking.event_id == event_id
            )
            .options(
                selectinload(Booking.vendor),
                selectinload(
                    Booking.participant_links
                ).selectinload(
                    BookingParticipant.participant
                ),
                selectinload(
                    Booking.table_assignment
                ).selectinload(
                    TableAssignment.table
                ),
            )
            .order_by(Booking.code)
        ).all()
    )


def build_report(
    db: Session,
    name: str,
    event_id: UUID | None,
) -> dict:
    if name not in REPORT_NAMES:
        raise HTTPException(
            status_code=404,
            detail="Unknown report",
        )

    event_id = _event_id(db, event_id)
    event = db.get(Event, event_id)

    if name == "vendors":
        return _vendors_report(
            db,
            event,
        )
    if name == "participants":
        return _participants_report(
            db,
            event,
        )
    if name == "seating":
        return _seating_report(
            db,
            event,
        )
    if name == "finance":
        return _finance_report(
            db,
            event,
        )
    return _checkin_report(
        db,
        event,
    )


def _base(
    event: Event,
    name: str,
    title: str,
    columns: list[dict],
    rows: list[dict],
) -> dict:
    return {
        "report": name,
        "title": title,
        "event": {
            "id": str(event.id),
            "code": event.code,
            "event_name": event.event_name,
            "currency": event.currency,
        },
        "columns": columns,
        "rows": rows,
    }


def _vendors_report(
    db: Session,
    event: Event,
) -> dict:
    rows = []
    for booking in _bookings(db, event.id):
        people = sum(
            1
            for link in booking.participant_links
            if link.registration_status
            != "CANCELLED"
        )
        rows.append({
            "Vendor": (
                booking.vendor.vendor_name
                if booking.vendor
                else ""
            ),
            "Table": _assignment_label(
                booking.table_assignment
            ),
            "Type": booking.booking_type,
            "People": people,
            "Total": float(
                booking.final_total or 0
            ),
            "Paid": float(
                booking.paid_amount or 0
            ),
            "Balance": float(
                booking.balance or 0
            ),
            "Status": booking.booking_status,
        })

    return _base(
        event,
        "vendors",
        "Вендоры",
        [
            {"key": "Vendor", "label": "Vendor"},
            {"key": "Table", "label": "Table"},
            {"key": "Type", "label": "Type"},
            {"key": "People", "label": "People"},
            {"key": "Total", "label": "Total"},
            {"key": "Paid", "label": "Paid"},
            {"key": "Balance", "label": "Balance"},
            {"key": "Status", "label": "Status"},
        ],
        rows,
    )


def _participants_report(
    db: Session,
    event: Event,
) -> dict:
    rows = []
    for booking in _bookings(db, event.id):
        table_label = _assignment_label(
            booking.table_assignment
        )

        for link in sorted(
            booking.participant_links,
            key=lambda item: item.sort_order,
        ):
            if (
                link.registration_status
                == "CANCELLED"
            ):
                continue

            person = link.participant
            rows.append({
                "LastName": person.last_name,
                "FirstName": person.first_name,
                "Nickname": person.nickname,
                "Vendor": (
                    booking.vendor.vendor_name
                    if booking.vendor
                    else ""
                ),
                "Table": table_label,
                "Role": link.role,
                "Included": (
                    "YES"
                    if link.is_included
                    else "NO"
                ),
                "CheckIn": link.checkin_status,
            })

    return _base(
        event,
        "participants",
        "Участники",
        [
            {"key": "LastName", "label": "LastName"},
            {"key": "FirstName", "label": "FirstName"},
            {"key": "Nickname", "label": "Nickname"},
            {"key": "Vendor", "label": "Vendor"},
            {"key": "Table", "label": "Table"},
            {"key": "Role", "label": "Role"},
            {"key": "Included", "label": "Included"},
            {"key": "CheckIn", "label": "CheckIn"},
        ],
        rows,
    )


def _seating_report(
    db: Session,
    event: Event,
) -> dict:
    zones = {
        zone.id: zone.zone_name
        for zone in db.scalars(
            select(LayoutZone).where(
                LayoutZone.event_id
                == event.id
            )
        ).all()
    }

    tables = db.scalars(
        select(LayoutTable)
        .where(
            LayoutTable.event_id == event.id
        )
        .options(
            selectinload(
                LayoutTable.assignments
            )
            .selectinload(
                TableAssignment.booking
            )
            .selectinload(Booking.vendor)
        )
        .order_by(LayoutTable.table_number)
    ).all()

    rows = []
    for table in tables:
        a = ""
        b = ""

        for assignment in table.assignments:
            if not assignment.active:
                continue

            booking = assignment.booking
            vendor = (
                booking.vendor.vendor_name
                if booking
                and booking.vendor
                else ""
            )

            if assignment.slot_count >= 2:
                a = vendor
                b = vendor
            elif assignment.start_slot == 1:
                a = vendor
            else:
                b = vendor

        rows.append({
            "Table": table.table_label,
            "A": a,
            "B": b,
            "Zone": (
                zones.get(table.zone_id, "")
                if table.zone_id
                else ""
            ),
        })

    return _base(
        event,
        "seating",
        "Рассадка",
        [
            {"key": "Table", "label": "Table"},
            {"key": "A", "label": "A"},
            {"key": "B", "label": "B"},
            {"key": "Zone", "label": "Zone"},
        ],
        rows,
    )


def _finance_report(
    db: Session,
    event: Event,
) -> dict:
    rows = []
    for booking in _bookings(db, event.id):
        rows.append({
            "Vendor": (
                booking.vendor.vendor_name
                if booking.vendor
                else ""
            ),
            "Table": _assignment_label(
                booking.table_assignment
            ),
            "Charged": float(
                booking.final_total or 0
            ),
            "Paid": float(
                booking.paid_amount or 0
            ),
            "Balance": float(
                booking.balance or 0
            ),
            "Status": booking.payment_status,
        })

    return _base(
        event,
        "finance",
        "Финансы",
        [
            {"key": "Vendor", "label": "Vendor"},
            {"key": "Table", "label": "Table"},
            {"key": "Charged", "label": "Charged"},
            {"key": "Paid", "label": "Paid"},
            {"key": "Balance", "label": "Balance"},
            {"key": "Status", "label": "Status"},
        ],
        rows,
    )


def _checkin_report(
    db: Session,
    event: Event,
) -> dict:
    rows = []
    for link in load_event_links(
        db,
        event.id,
    ):
        item = participant_row(link)
        rows.append({
            "Vendor": item["vendor_name"],
            "Table": item["table_label"] or "",
            "LastName": item["last_name"],
            "FirstName": item["first_name"],
            "Nickname": item["nickname"],
            "Role": item["role"],
            "CheckIn": item["checkin_status"],
            "CheckInTime": (
                item["checkin_time"].isoformat()
                if item["checkin_time"]
                else ""
            ),
            "Badge": (
                item["badge_number"]
                if item["badge_issued"]
                and item["badge_number"]
                else (
                    "ISSUED"
                    if item["badge_issued"]
                    else ""
                )
            ),
        })

    return _base(
        event,
        "checkin",
        "Check-in",
        [
            {"key": "Vendor", "label": "Vendor"},
            {"key": "Table", "label": "Table"},
            {"key": "LastName", "label": "LastName"},
            {"key": "FirstName", "label": "FirstName"},
            {"key": "Nickname", "label": "Nickname"},
            {"key": "Role", "label": "Role"},
            {"key": "CheckIn", "label": "CheckIn"},
            {"key": "CheckInTime", "label": "CheckInTime"},
            {"key": "Badge", "label": "Badge"},
        ],
        rows,
    )
