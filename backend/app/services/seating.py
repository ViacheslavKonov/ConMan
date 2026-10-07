from math import floor
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.core import (
    Booking,
    BookingParticipant,
    LayoutTable,
    LayoutZone,
    TableAssignment,
)
from app.services.codes import next_code
from app.services.core import booking_dict, current_event_id


SEATABLE_STATUSES = ["SUBMITTED", "APPROVED", "AWAITING_PAYMENT", "CONFIRMED"]


def zone_dict(zone: LayoutZone) -> dict:
    return {
        "id": str(zone.id),
        "code": zone.code,
        "event_id": str(zone.event_id),
        "zone_name": zone.zone_name,
        "zone_type": zone.zone_type,
        "color": zone.color,
        "x": zone.x,
        "y": zone.y,
        "width": zone.width,
        "height": zone.height,
        "sort_order": zone.sort_order,
        "active": zone.active,
        "notes": zone.notes,
    }


def table_dict(table: LayoutTable) -> dict:
    return {
        "id": str(table.id),
        "code": table.code,
        "event_id": str(table.event_id),
        "zone_id": str(table.zone_id) if table.zone_id else None,
        "table_number": table.table_number,
        "table_label": table.table_label,
        "capacity_slots": table.capacity_slots,
        "x": table.x,
        "y": table.y,
        "width": table.width,
        "height": table.height,
        "sort_order": table.sort_order,
        "active": table.active,
        "notes": table.notes,
    }


def assignment_dict(assignment: TableAssignment) -> dict:
    return {
        "id": str(assignment.id),
        "code": assignment.code,
        "event_id": str(assignment.event_id),
        "table_id": str(assignment.table_id),
        "booking_id": str(assignment.booking_id),
        "start_slot": assignment.start_slot,
        "slot_count": assignment.slot_count,
        "active": assignment.active,
        "notes": assignment.notes,
        "booking": booking_dict(assignment.booking, include_details=True) if assignment.booking else None,
    }


def _booking_options():
    return [
        selectinload(Booking.vendor),
        selectinload(Booking.tariff),
        selectinload(Booking.participant_links).selectinload(BookingParticipant.participant),
        selectinload(Booking.charges),
        selectinload(Booking.payments),
    ]


def seating_overview(db: Session, event_id: UUID | None) -> dict:
    event_id = event_id or current_event_id(db)

    if not event_id:
        return {
            "event_id": None,
            "zones": [],
            "tables": [],
            "assignments": [],
            "unassigned_bookings": [],
            "authors_groups": [],
        }

    zones = db.scalars(
        select(LayoutZone)
        .where(LayoutZone.event_id == event_id)
        .order_by(LayoutZone.sort_order, LayoutZone.zone_name)
    ).all()

    tables = db.scalars(
        select(LayoutTable)
        .where(
            LayoutTable.event_id == event_id,
            LayoutTable.active.is_(True),
        )
        .order_by(LayoutTable.table_number, LayoutTable.sort_order)
    ).all()

    assignments = db.scalars(
        select(TableAssignment)
        .where(
            TableAssignment.event_id == event_id,
            TableAssignment.active.is_(True),
        )
        .options(
            selectinload(TableAssignment.booking).selectinload(Booking.vendor),
            selectinload(TableAssignment.booking).selectinload(Booking.tariff),
            selectinload(TableAssignment.booking)
            .selectinload(Booking.participant_links)
            .selectinload(BookingParticipant.participant),
            selectinload(TableAssignment.booking).selectinload(Booking.charges),
            selectinload(TableAssignment.booking).selectinload(Booking.payments),
            selectinload(TableAssignment.table),
        )
    ).all()

    assigned_booking_ids = {item.booking_id for item in assignments}

    unassigned = db.scalars(
        select(Booking)
        .where(
            Booking.event_id == event_id,
            Booking.booking_status.in_(SEATABLE_STATUSES),
            Booking.id.notin_(list(assigned_booking_ids)) if assigned_booking_ids else True,
        )
        .options(*_booking_options())
        .order_by(Booking.booking_status, Booking.code)
    ).all()

    author_entries = []
    for assignment in sorted(assignments, key=lambda item: (item.table.table_number if item.table else 0, item.start_slot)):
        if not assignment.table or not assignment.booking:
            continue

        label = assignment.table.table_label
        if assignment.slot_count == 1 and assignment.table.capacity_slots > 1:
            suffix = "A" if assignment.start_slot == 1 else "B"
            label = f"{label}{suffix}"

        author_entries.append({
            "label": label,
            "table_number": assignment.table.table_number,
            "sort_order": assignment.start_slot,
            "vendor_name": assignment.booking.vendor.vendor_name if assignment.booking.vendor else assignment.booking.code,
            "booking_type": assignment.booking.booking_type,
            "payment_status": assignment.booking.payment_status,
        })

    groups = []
    if author_entries:
        max_number = max(item["table_number"] for item in author_entries)
        bucket_count = floor((max_number - 1) / 16) + 1
        for bucket in range(bucket_count):
            start = bucket * 16 + 1
            end = min(start + 15, max_number)
            items = [
                item for item in author_entries
                if start <= item["table_number"] <= end
            ]
            if items:
                groups.append({
                    "title": f"Столы {start}-{end}",
                    "items": items,
                })

    return {
        "event_id": str(event_id),
        "zones": [zone_dict(zone) for zone in zones],
        "tables": [table_dict(table) for table in tables],
        "assignments": [assignment_dict(item) for item in assignments],
        "unassigned_bookings": [booking_dict(item, include_details=True) for item in unassigned],
        "authors_groups": groups,
    }


def update_booking_seating_status(db: Session, booking: Booking | None) -> None:
    if not booking:
        return

    current = db.scalar(
        select(TableAssignment).where(
            TableAssignment.booking_id == booking.id,
            TableAssignment.active.is_(True),
        )
    )
    booking.seating_status = "ASSIGNED" if current else "UNASSIGNED"
    db.flush()


def slots_for_assignment(assignment: TableAssignment) -> set[int]:
    return set(range(assignment.start_slot, assignment.start_slot + assignment.slot_count))


def can_place(
    assignment: TableAssignment | None,
    table: LayoutTable,
    start_slot: int,
    slot_count: int,
    exclude_booking_ids: set[UUID] | None = None,
) -> bool:
    exclude_booking_ids = exclude_booking_ids or set()
    target = set(range(start_slot, start_slot + slot_count))
    if min(target) < 1 or max(target) > table.capacity_slots:
        return False

    for existing in table.assignments:
        if not existing.active or existing.booking_id in exclude_booking_ids:
            continue
        if target & slots_for_assignment(existing):
            return False
    return True


def get_table(db: Session, table_id: UUID) -> LayoutTable:
    table = db.scalar(
        select(LayoutTable)
        .where(LayoutTable.id == table_id)
        .options(selectinload(LayoutTable.assignments))
    )
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    return table


def get_booking(db: Session, booking_id: UUID) -> Booking:
    booking = db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(*_booking_options(), selectinload(Booking.table_assignment))
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking


def place_booking(
    db: Session,
    booking_id: UUID,
    table_id: UUID,
    start_slot: int,
    actor_id: UUID | None,
) -> dict:
    booking = get_booking(db, booking_id)
    table = db.scalar(
        select(LayoutTable)
        .where(LayoutTable.id == table_id)
        .options(
            selectinload(LayoutTable.assignments).selectinload(TableAssignment.booking).selectinload(Booking.vendor),
            selectinload(LayoutTable.assignments).selectinload(TableAssignment.booking).selectinload(Booking.tariff),
            selectinload(LayoutTable.assignments).selectinload(TableAssignment.booking).selectinload(Booking.participant_links).selectinload(BookingParticipant.participant),
            selectinload(LayoutTable.assignments).selectinload(TableAssignment.booking).selectinload(Booking.charges),
            selectinload(LayoutTable.assignments).selectinload(TableAssignment.booking).selectinload(Booking.payments),
        )
    )
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if booking.event_id != table.event_id:
        raise HTTPException(status_code=409, detail="Booking and table belong to different events")

    if booking.booking_status not in SEATABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Booking status is not seatable")

    slot_count = 2 if booking.booking_type == "FULL" else 1
    if slot_count == 2:
        start_slot = 1
    if start_slot < 1 or start_slot > table.capacity_slots:
        raise HTTPException(status_code=409, detail="Invalid target slot")
    if start_slot + slot_count - 1 > table.capacity_slots:
        raise HTTPException(status_code=409, detail="Booking does not fit into target table")

    old_assignment = booking.table_assignment
    target_slots = set(range(start_slot, start_slot + slot_count))
    conflicts = [
        item for item in table.assignments
        if item.active and item.booking_id != booking.id and target_slots & slots_for_assignment(item)
    ]

    if conflicts:
        if not old_assignment or len(conflicts) != 1:
            raise HTTPException(status_code=409, detail="Target table slot is already occupied")
        conflicting = conflicts[0]
        old_table = db.scalar(
            select(LayoutTable)
            .where(LayoutTable.id == old_assignment.table_id)
            .options(selectinload(LayoutTable.assignments))
        )
        if not old_table:
            raise HTTPException(status_code=409, detail="Cannot load source table for swap")
        if not can_place(
            conflicting,
            old_table,
            old_assignment.start_slot,
            conflicting.slot_count,
            exclude_booking_ids={booking.id, conflicting.booking_id},
        ):
            raise HTTPException(status_code=409, detail="Automatic swap is not possible")

        conflicting.table_id = old_table.id
        conflicting.event_id = old_table.event_id
        conflicting.start_slot = old_assignment.start_slot
        conflicting.updated_by = actor_id
        update_booking_seating_status(db, conflicting.booking)

    if old_assignment:
        old_assignment.table_id = table.id
        old_assignment.event_id = table.event_id
        old_assignment.start_slot = start_slot
        old_assignment.slot_count = slot_count
        old_assignment.updated_by = actor_id
        assignment = old_assignment
    else:
        assignment = TableAssignment(
            code=next_code(db, "ASN"),
            event_id=table.event_id,
            table_id=table.id,
            booking_id=booking.id,
            start_slot=start_slot,
            slot_count=slot_count,
            active=True,
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(assignment)

    booking.seating_status = "ASSIGNED"
    booking.updated_by = actor_id
    db.flush()
    return assignment_dict(assignment)


def unassign_booking(
    db: Session,
    booking_id: UUID,
    actor_id: UUID | None,
) -> None:
    booking = get_booking(db, booking_id)
    assignment = booking.table_assignment
    if not assignment or not assignment.active:
        return

    db.delete(assignment)
    booking.seating_status = "UNASSIGNED"
    booking.updated_by = actor_id
    db.flush()
