from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.audit import audit
from app.db import get_db
from app.dependencies import CsrfDep, require_roles
from app.models.core import (
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
from app.models.user import User, UserRole
from app.schemas.admin import (
    BookingAdminUpdate,
    ChargeDeactivateInput,
    PaymentCancelInput,
)
from app.services.admin_data import (
    apply_booking_admin_update,
    cancel_payment_record,
    cleanup_orphan_participants,
    clear_or_replace_current_event,
    deactivate_manual_charge,
    delete_booking_cascade,
    load_booking_for_delete,
    management_state,
)
from app.services.core import (
    booking_dict,
    event_dict,
    participant_dict,
    tariff_dict,
    vendor_dict,
)
from app.services.seating import table_dict, zone_dict


router = APIRouter(
    prefix="/admin/data",
    tags=["admin-data"],
)


def admin_user():
    return require_roles(
        UserRole.ADMIN.value,
        UserRole.MANAGER.value,
    )


@router.get("")
def read_management_state(
    event_id: UUID | None = None,
    _: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    return management_state(db, event_id)


@router.patch("/bookings/{booking_id}")
def admin_update_booking(
    booking_id: UUID,
    payload: BookingAdminUpdate,
    _: CsrfDep,
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    booking = db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
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
        )
    )
    if not booking:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    before = booking_dict(
        booking,
        include_details=True,
    )

    fields = payload.model_fields_set
    apply_booking_admin_update(
        db,
        booking,
        payload.vendor_id,
        payload.tariff_id,
        "notes" in fields,
        payload.notes,
        user.id,
    )

    db.flush()
    after = booking_dict(booking)

    audit(
        db,
        user_id=user.id,
        entity_type="BOOKING",
        entity_id=str(booking.id),
        action="ADMIN_UPDATE",
        before=before,
        after=after,
    )
    db.commit()

    return after


@router.delete("/bookings/{booking_id}")
def admin_delete_booking(
    booking_id: UUID,
    _: CsrfDep,
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    booking = load_booking_for_delete(
        db,
        booking_id,
    )
    before = {
        "id": str(booking.id),
        "code": booking.code,
        "event_id": str(booking.event_id),
        "vendor_id": str(booking.vendor_id),
    }

    summary = delete_booking_cascade(
        db,
        booking,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="BOOKING",
        entity_id=str(booking_id),
        action="DELETE_CASCADE",
        before=before,
        metadata=summary,
    )
    db.commit()
    return {
        "ok": True,
        "cascade": summary,
    }


@router.delete("/events/{event_id}")
def admin_delete_event(
    event_id: UUID,
    _: CsrfDep,
    cascade: bool = Query(default=False),
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    booking_ids = list(
        db.scalars(
            select(Booking.id).where(
                Booking.event_id == event_id
            )
        ).all()
    )
    counts = {
        "bookings": len(booking_ids),
        "tariffs": int(
            db.scalar(
                select(func.count())
                .select_from(Tariff)
                .where(
                    Tariff.event_id == event_id
                )
            )
            or 0
        ),
        "zones": int(
            db.scalar(
                select(func.count())
                .select_from(LayoutZone)
                .where(
                    LayoutZone.event_id
                    == event_id
                )
            )
            or 0
        ),
        "tables": int(
            db.scalar(
                select(func.count())
                .select_from(LayoutTable)
                .where(
                    LayoutTable.event_id
                    == event_id
                )
            )
            or 0
        ),
    }

    if (
        not cascade
        and any(counts.values())
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Event contains dependent "
                    "objects. Repeat with "
                    "cascade=true to delete them."
                ),
                "dependencies": counts,
            },
        )

    participant_ids: set[UUID] = set()

    if booking_ids:
        participant_ids = set(
            db.scalars(
                select(
                    BookingParticipant.participant_id
                ).where(
                    BookingParticipant.booking_id.in_(
                        booking_ids
                    )
                )
            ).all()
        )

    before = event_dict(event)
    replacement = (
        clear_or_replace_current_event(
            db,
            event_id,
        )
    )

    # Database-level CASCADE removes event-specific
    # tariffs/bookings/charges/payments/layout/check-in.
    # Participant masters are event-independent,
    # so orphan cleanup is explicit below.
    db.delete(event)
    db.flush()

    orphan_count = cleanup_orphan_participants(
        db,
        participant_ids,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="EVENT",
        entity_id=str(event_id),
        action="DELETE_CASCADE",
        before=before,
        metadata={
            **counts,
            "orphan_participants_deleted":
                orphan_count,
            "new_current_event_id":
                replacement,
        },
    )
    db.commit()

    return {
        "ok": True,
        "cascade": {
            **counts,
            "orphan_participants_deleted":
                orphan_count,
        },
        "current_event_id": replacement,
    }


@router.delete("/tariffs/{tariff_id}")
def admin_delete_tariff(
    tariff_id: UUID,
    _: CsrfDep,
    cascade: bool = Query(default=False),
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    tariff = db.get(Tariff, tariff_id)
    if not tariff:
        raise HTTPException(
            status_code=404,
            detail="Tariff not found",
        )

    bookings = db.scalars(
        select(Booking)
        .where(Booking.tariff_id == tariff_id)
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
    ).all()

    if bookings and not cascade:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Tariff is used by bookings. "
                    "Deactivate it or repeat with "
                    "cascade=true."
                ),
                "bookings": len(bookings),
            },
        )

    before = tariff_dict(tariff)
    cascade_rows = []
    for booking in bookings:
        cascade_rows.append(
            delete_booking_cascade(
                db,
                booking,
            )
        )

    db.delete(tariff)
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="TARIFF",
        entity_id=str(tariff_id),
        action="DELETE_CASCADE",
        before=before,
        metadata={
            "bookings_deleted":
                len(cascade_rows),
        },
    )
    db.commit()
    return {
        "ok": True,
        "bookings_deleted":
            len(cascade_rows),
    }


@router.delete("/vendors/{vendor_id}")
def admin_delete_vendor(
    vendor_id: UUID,
    _: CsrfDep,
    cascade: bool = Query(default=False),
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=404,
            detail="Vendor not found",
        )

    bookings = db.scalars(
        select(Booking)
        .where(
            Booking.vendor_id == vendor_id
        )
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
    ).all()

    if bookings and not cascade:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Vendor has bookings. "
                    "Deactivate it or repeat with "
                    "cascade=true."
                ),
                "bookings": len(bookings),
            },
        )

    before = vendor_dict(vendor)
    deleted_bookings = 0
    for booking in bookings:
        delete_booking_cascade(
            db,
            booking,
        )
        deleted_bookings += 1

    db.delete(vendor)
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="VENDOR",
        entity_id=str(vendor_id),
        action="DELETE_CASCADE",
        before=before,
        metadata={
            "bookings_deleted":
                deleted_bookings,
        },
    )
    db.commit()
    return {
        "ok": True,
        "bookings_deleted":
            deleted_bookings,
    }


@router.delete("/participants/{participant_id}")
def admin_delete_participant(
    participant_id: UUID,
    _: CsrfDep,
    cascade: bool = Query(default=False),
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    participant = db.get(
        Participant,
        participant_id,
    )
    if not participant:
        raise HTTPException(
            status_code=404,
            detail="Participant not found",
        )

    links = db.scalars(
        select(BookingParticipant)
        .where(
            BookingParticipant.participant_id
            == participant_id
        )
        .options(
            selectinload(
                BookingParticipant.booking
            )
        )
    ).all()

    if links and not cascade:
        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "Participant is linked to "
                    "bookings. Repeat with "
                    "cascade=true to remove links."
                ),
                "booking_links": len(links),
            },
        )

    before = participant_dict(participant)
    affected_bookings = {
        link.booking
        for link in links
        if link.booking
    }

    for link in links:
        db.delete(link)
    db.flush()

    for booking in affected_bookings:
        from app.services.core import (
            recalculate_booking,
        )
        recalculate_booking(
            db,
            booking,
            user.id,
        )

    db.delete(participant)
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="PARTICIPANT",
        entity_id=str(participant_id),
        action="DELETE_CASCADE",
        before=before,
        metadata={
            "booking_links_deleted":
                len(links),
        },
    )
    db.commit()
    return {
        "ok": True,
        "booking_links_deleted":
            len(links),
    }


@router.delete("/zones/{zone_id}")
def admin_delete_zone(
    zone_id: UUID,
    _: CsrfDep,
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    zone = db.get(LayoutZone, zone_id)
    if not zone:
        raise HTTPException(
            status_code=404,
            detail="Zone not found",
        )

    tables = db.scalars(
        select(LayoutTable).where(
            LayoutTable.zone_id == zone_id
        )
    ).all()

    before = zone_dict(zone)
    for table in tables:
        table.zone_id = None
        table.updated_by = user.id

    db.delete(zone)
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="LAYOUT_ZONE",
        entity_id=str(zone_id),
        action="DELETE",
        before=before,
        metadata={
            "tables_unlinked":
                len(tables),
        },
    )
    db.commit()
    return {
        "ok": True,
        "tables_unlinked": len(tables),
    }


@router.delete("/tables/{table_id}")
def admin_delete_table(
    table_id: UUID,
    _: CsrfDep,
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    table = db.scalar(
        select(LayoutTable)
        .where(LayoutTable.id == table_id)
        .options(
            selectinload(
                LayoutTable.assignments
            ).selectinload(
                TableAssignment.booking
            )
        )
    )
    if not table:
        raise HTTPException(
            status_code=404,
            detail="Table not found",
        )

    before = table_dict(table)
    assigned = 0
    for assignment in table.assignments:
        if assignment.booking:
            assignment.booking.seating_status = (
                "UNASSIGNED"
            )
            assignment.booking.updated_by = user.id
        assigned += 1

    db.delete(table)
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="LAYOUT_TABLE",
        entity_id=str(table_id),
        action="DELETE_CASCADE",
        before=before,
        metadata={
            "assignments_removed":
                assigned,
        },
    )
    db.commit()
    return {
        "ok": True,
        "assignments_removed": assigned,
    }


@router.delete("/payments/{payment_id}")
def admin_cancel_payment(
    payment_id: UUID,
    payload: PaymentCancelInput | None,
    _: CsrfDep,
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment not found",
        )

    before = {
        "status": payment.status,
        "amount": str(payment.amount),
        "payment_type":
            payment.payment_type,
    }
    booking = cancel_payment_record(
        db,
        payment,
        user.id,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="PAYMENT",
        entity_id=str(payment.id),
        action="CANCEL",
        before=before,
        after={
            "status": payment.status,
        },
        metadata={
            "reason":
                payload.reason
                if payload
                else None,
        },
    )
    db.commit()
    return {
        "ok": True,
        "booking": booking_dict(booking),
    }


@router.delete("/charges/{charge_id}")
def admin_deactivate_charge(
    charge_id: UUID,
    payload: ChargeDeactivateInput | None,
    _: CsrfDep,
    user: User = Depends(admin_user()),
    db: Session = Depends(get_db),
):
    charge = db.get(Charge, charge_id)
    if not charge:
        raise HTTPException(
            status_code=404,
            detail="Charge not found",
        )

    before = {
        "active": charge.active,
        "amount": str(charge.amount),
        "charge_type":
            charge.charge_type,
    }
    booking = deactivate_manual_charge(
        db,
        charge,
        user.id,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="CHARGE",
        entity_id=str(charge.id),
        action="DEACTIVATE",
        before=before,
        after={
            "active": charge.active,
        },
        metadata={
            "reason":
                payload.reason
                if payload
                else None,
        },
    )
    db.commit()
    return {
        "ok": True,
        "booking": booking_dict(booking),
    }
