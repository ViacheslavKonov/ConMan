from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.dependencies import CsrfDep, require_roles
from app.models.core import LayoutTable, LayoutZone
from app.models.user import User, UserRole
from app.schemas.step4 import (
    AssignBookingInput,
    BulkTableCreate,
    LayoutTableUpdate,
    LayoutZoneCreate,
    LayoutZoneUpdate,
    UnassignBookingInput,
)
from app.services.codes import next_code
from app.services.core import current_event_id
from app.services.seating import place_booking, seating_overview, table_dict, zone_dict

router = APIRouter(tags=["seating"])

SEATING_VIEW_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.REGISTRATION.value,
    UserRole.VIEWER.value,
]

SEATING_EDIT_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
]

SEATING_ASSIGN_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.REGISTRATION.value,
]

def seating_view_user():
    return require_roles(*SEATING_VIEW_ROLES)

def seating_edit_user():
    return require_roles(*SEATING_EDIT_ROLES)

def seating_assign_user():
    return require_roles(*SEATING_ASSIGN_ROLES)


@router.get("/seating/layout")
def get_layout(
    db: Session = Depends(get_db),
    event_id: UUID | None = Query(default=None),
    user: User = Depends(seating_view_user()),
):
    return seating_overview(db, event_id)


@router.post("/seating/zones")
def create_zone(
    payload: LayoutZoneCreate,
    _: CsrfDep,
    user: User = Depends(seating_edit_user()),
    db: Session = Depends(get_db),
):
    event_id = current_event_id(db)
    if not event_id:
        raise HTTPException(status_code=409, detail="Current event is not selected")

    zone = LayoutZone(
        code=next_code(db, "ZON"),
        event_id=event_id,
        zone_name=payload.zone_name.strip(),
        zone_type=payload.zone_type.strip().upper(),
        color=payload.color,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        sort_order=payload.sort_order,
        notes=payload.notes,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(zone)
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="layout_zone",
        entity_id=str(zone.id),
        action="create",
        after=zone_dict(zone),
    )
    db.commit()
    return zone_dict(zone)


@router.patch("/seating/zones/{zone_id}")
def update_zone(
    zone_id: UUID,
    payload: LayoutZoneUpdate,
    _: CsrfDep,
    user: User = Depends(seating_edit_user()),
    db: Session = Depends(get_db),
):
    zone = db.get(LayoutZone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    before = zone_dict(zone)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    zone.updated_by = user.id
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="layout_zone",
        entity_id=str(zone.id),
        action="update",
        before=before,
        after=zone_dict(zone),
    )
    db.commit()
    return zone_dict(zone)


@router.post("/seating/tables/bulk")
def create_tables_bulk(
    payload: BulkTableCreate,
    _: CsrfDep,
    user: User = Depends(seating_edit_user()),
    db: Session = Depends(get_db),
):
    event_id = current_event_id(db)
    if not event_id:
        raise HTTPException(status_code=409, detail="Current event is not selected")

    existing_numbers = {
        row[0]
        for row in db.execute(
            select(LayoutTable.table_number).where(LayoutTable.event_id == event_id)
        ).all()
    }

    created = []
    x = payload.start_x
    y = payload.start_y

    for index in range(payload.count):
        number = payload.start_number + index
        if number in existing_numbers:
            raise HTTPException(
                status_code=409,
                detail=f"Table number {number} already exists",
            )

        row = index // payload.columns
        col = index % payload.columns
        item_x = payload.start_x + col * (payload.width + payload.x_gap)
        item_y = payload.start_y + row * (payload.height + payload.y_gap)

        label = f"{payload.numbering_prefix or ''}{number}"
        table = LayoutTable(
            code=next_code(db, "TBL"),
            event_id=event_id,
            zone_id=UUID(payload.zone_id) if payload.zone_id else None,
            table_number=number,
            table_label=label,
            capacity_slots=payload.capacity_slots,
            x=item_x,
            y=item_y,
            width=payload.width,
            height=payload.height,
            sort_order=index,
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(table)
        created.append(table)
        existing_numbers.add(number)

    db.flush()
    rows = [table_dict(item) for item in created]
    audit(
        db,
        user_id=user.id,
        entity_type="layout_table",
        entity_id=None,
        action="bulk_create",
        after={"count": len(rows), "items": rows},
    )
    db.commit()
    return {"items": rows}


@router.patch("/seating/tables/{table_id}")
def update_table(
    table_id: UUID,
    payload: LayoutTableUpdate,
    _: CsrfDep,
    user: User = Depends(seating_edit_user()),
    db: Session = Depends(get_db),
):
    table = db.get(LayoutTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    before = table_dict(table)
    data = payload.model_dump(exclude_unset=True)
    if "zone_id" in data:
        table.zone_id = UUID(data.pop("zone_id")) if data["zone_id"] else None

    for field, value in data.items():
        setattr(table, field, value)
    table.updated_by = user.id
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="layout_table",
        entity_id=str(table.id),
        action="update",
        before=before,
        after=table_dict(table),
    )
    db.commit()
    return table_dict(table)


@router.post("/seating/assignments/assign")
def assign_booking(
    payload: AssignBookingInput,
    _: CsrfDep,
    user: User = Depends(seating_assign_user()),
    db: Session = Depends(get_db),
):
    data = place_booking(
        db,
        booking_id=UUID(payload.booking_id),
        table_id=UUID(payload.table_id),
        start_slot=payload.start_slot,
        actor_id=user.id,
    )
    audit(
        db,
        user_id=user.id,
        entity_type="table_assignment",
        entity_id=data["id"],
        action="assign",
        after=data,
    )
    db.commit()
    return data


@router.post("/seating/assignments/unassign")
def unassign_assignment(
    payload: UnassignBookingInput,
    _: CsrfDep,
    user: User = Depends(seating_assign_user()),
    db: Session = Depends(get_db),
):
    from app.services.seating import unassign_booking

    unassign_booking(db, UUID(payload.booking_id), user.id)
    audit(
        db,
        user_id=user.id,
        entity_type="table_assignment",
        entity_id=payload.booking_id,
        action="unassign",
        after={"booking_id": payload.booking_id},
    )
    db.commit()
    return {"ok": True}
