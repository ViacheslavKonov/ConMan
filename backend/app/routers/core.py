from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.audit import audit
from app.db import get_db
from app.dependencies import CsrfDep, UserDep, require_roles
from app.models.core import (
    Booking,
    BookingParticipant,
    Event,
    Participant,
    Tariff,
    Vendor,
)
from app.models.user import User, UserRole
from app.schemas.core import (
    BookingCreate,
    BookingParticipantCreate,
    BookingTransition,
    EventCreate,
    EventUpdate,
    ParticipantUpdate,
    TariffCreate,
    TariffUpdate,
    VendorCreate,
    VendorUpdate,
)
from app.services.codes import next_code
from app.services.core import (
    booking_dict,
    booking_with_details,
    current_event_id,
    event_dict,
    get_current_event,
    money,
    participant_dict,
    recalculate_booking,
    set_current_event,
    tariff_dict,
    transition_booking,
    vendor_dict,
)


router = APIRouter(tags=["core"])

READ_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.REGISTRATION.value,
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


@router.get("/events")
def list_events(
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    events = db.scalars(
        select(Event).order_by(Event.start_date.desc(), Event.event_name)
    ).all()

    current = current_event_id(db)

    return {
        "current_event_id": str(current) if current else None,
        "items": [event_dict(event) for event in events],
    }


@router.post("/events", status_code=201)
def create_event(
    payload: EventCreate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    event = Event(
        code=next_code(db, "EVT"),
        event_name=payload.event_name.strip(),
        start_date=payload.start_date,
        end_date=payload.end_date,
        venue=payload.venue,
        city=payload.city,
        currency=payload.currency.upper(),
        status=payload.status,
        registration_open=payload.registration_open,
        vendor_checkin_open=payload.vendor_checkin_open,
        seating_preferences_open=payload.seating_preferences_open,
        notes=payload.notes,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(event)
    db.flush()

    if current_event_id(db) is None:
        set_current_event(db, event.id)

    audit(
        db,
        user_id=user.id,
        entity_type="EVENT",
        entity_id=str(event.id),
        action="CREATE",
        after=event_dict(event),
    )

    db.commit()
    db.refresh(event)

    return event_dict(event)


@router.get("/events/current")
def read_current_event(
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    event = get_current_event(db)
    return {"event": event_dict(event) if event else None}


@router.put("/events/current/{event_id}")
def switch_current_event(
    event_id: UUID,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    event = set_current_event(db, event_id)

    audit(
        db,
        user_id=user.id,
        entity_type="EVENT",
        entity_id=str(event.id),
        action="UPDATE",
        metadata={"current_event": True},
    )

    db.commit()
    return {"event": event_dict(event)}


@router.patch("/events/{event_id}")
def update_event(
    event_id: UUID,
    payload: EventUpdate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    before = event_dict(event)
    changes = payload.model_dump(exclude_unset=True)

    for field, value in changes.items():
        if field == "currency" and value:
            value = value.upper()
        setattr(event, field, value)

    if event.end_date < event.start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be >= start_date",
        )

    event.updated_by = user.id
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="EVENT",
        entity_id=str(event.id),
        action="UPDATE",
        before=before,
        after=event_dict(event),
    )

    db.commit()
    return event_dict(event)


@router.get("/events/{event_id}/tariffs")
def list_tariffs(
    event_id: UUID,
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    if not db.get(Event, event_id):
        raise HTTPException(status_code=404, detail="Event not found")

    tariffs = db.scalars(
        select(Tariff)
        .where(Tariff.event_id == event_id)
        .order_by(Tariff.booking_type, Tariff.valid_from.desc())
    ).all()

    return {"items": [tariff_dict(item) for item in tariffs]}


@router.post("/events/{event_id}/tariffs", status_code=201)
def create_tariff(
    event_id: UUID,
    payload: TariffCreate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    if not db.get(Event, event_id):
        raise HTTPException(status_code=404, detail="Event not found")

    tariff = Tariff(
        code=next_code(db, "TRF"),
        event_id=event_id,
        tariff_name=payload.tariff_name.strip(),
        booking_type=payload.booking_type,
        base_price=payload.base_price,
        included_helpers=payload.included_helpers,
        extra_participant_price=payload.extra_participant_price,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        active=payload.active,
        notes=payload.notes,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(tariff)
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="TARIFF",
        entity_id=str(tariff.id),
        action="CREATE",
        after=tariff_dict(tariff),
    )

    db.commit()
    return tariff_dict(tariff)


@router.patch("/tariffs/{tariff_id}")
def update_tariff(
    tariff_id: UUID,
    payload: TariffUpdate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    tariff = db.get(Tariff, tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")

    before = tariff_dict(tariff)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tariff, field, value)

    if tariff.valid_to and tariff.valid_to < tariff.valid_from:
        raise HTTPException(
            status_code=422,
            detail="valid_to must be >= valid_from",
        )

    tariff.updated_by = user.id
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="TARIFF",
        entity_id=str(tariff.id),
        action="UPDATE",
        before=before,
        after=tariff_dict(tariff),
    )

    db.commit()
    return tariff_dict(tariff)


@router.get("/vendors")
def list_vendors(
    q: str | None = Query(default=None, max_length=200),
    active: bool | None = None,
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    stmt = select(Vendor)

    if active is not None:
        stmt = stmt.where(Vendor.active.is_(active))

    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Vendor.vendor_name.ilike(pattern),
                Vendor.email.ilike(pattern),
                Vendor.telegram.ilike(pattern),
                Vendor.code.ilike(pattern),
            )
        )

    vendors = db.scalars(
        stmt.order_by(Vendor.vendor_name).limit(300)
    ).all()

    return {"items": [vendor_dict(vendor) for vendor in vendors]}


@router.post("/vendors", status_code=201)
def create_vendor(
    payload: VendorCreate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    vendor = Vendor(
        code=next_code(db, "VND"),
        vendor_name=payload.vendor_name.strip(),
        legal_name=payload.legal_name,
        email=str(payload.email).lower(),
        phone=payload.phone,
        telegram=payload.telegram,
        website=payload.website,
        social_link=payload.social_link,
        description=payload.description,
        notes=payload.notes,
        active=payload.active,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(vendor)
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="VENDOR",
        entity_id=str(vendor.id),
        action="CREATE",
        after=vendor_dict(vendor),
    )

    db.commit()
    return vendor_dict(vendor)


@router.patch("/vendors/{vendor_id}")
def update_vendor(
    vendor_id: UUID,
    payload: VendorUpdate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    before = vendor_dict(vendor)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "email" and value is not None:
            value = str(value).lower()
        setattr(vendor, field, value)

    vendor.updated_by = user.id
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="VENDOR",
        entity_id=str(vendor.id),
        action="UPDATE",
        before=before,
        after=vendor_dict(vendor),
    )

    db.commit()
    return vendor_dict(vendor)


@router.get("/vendors/{vendor_id}")
def vendor_details(
    vendor_id: UUID,
    event_id: UUID | None = None,
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if event_id is None:
        event_id = current_event_id(db)

    stmt = (
        select(Booking)
        .where(Booking.vendor_id == vendor_id)
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

    if event_id:
        stmt = stmt.where(Booking.event_id == event_id)

    bookings = db.scalars(stmt).all()

    return {
        "vendor": vendor_dict(vendor),
        "bookings": [
            booking_dict(booking, include_details=True)
            for booking in bookings
        ],
    }


@router.get("/bookings")
def list_bookings(
    event_id: UUID | None = None,
    vendor_id: UUID | None = None,
    booking_status: str | None = None,
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    if event_id is None:
        event_id = current_event_id(db)

    stmt = (
        select(Booking)
        .options(selectinload(Booking.vendor))
        .order_by(Booking.application_date.desc())
    )

    if event_id:
        stmt = stmt.where(Booking.event_id == event_id)
    if vendor_id:
        stmt = stmt.where(Booking.vendor_id == vendor_id)
    if booking_status:
        stmt = stmt.where(Booking.booking_status == booking_status)

    bookings = db.scalars(stmt.limit(500)).all()

    items = []
    for booking in bookings:
        item = booking_dict(booking)
        item["vendor_name"] = booking.vendor.vendor_name if booking.vendor else ""
        items.append(item)

    return {"items": items}


@router.post("/bookings", status_code=201)
def create_booking(
    payload: BookingCreate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    event = db.get(Event, payload.event_id)
    vendor = db.get(Vendor, payload.vendor_id)
    tariff = db.get(Tariff, payload.tariff_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if not tariff:
        raise HTTPException(status_code=404, detail="Tariff not found")
    if tariff.event_id != event.id:
        raise HTTPException(status_code=409, detail="Tariff belongs to another event")
    if not tariff.active:
        raise HTTPException(status_code=409, detail="Tariff is inactive")

    duplicate = db.scalar(
        select(Booking).where(
            Booking.event_id == event.id,
            Booking.vendor_id == vendor.id,
            Booking.booking_status.notin_(["CANCELLED", "REJECTED"]),
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vendor already has active booking {duplicate.code} for this event",
        )

    booking = Booking(
        code=next_code(db, "BKG"),
        event_id=event.id,
        vendor_id=vendor.id,
        tariff_id=tariff.id,
        booking_type=tariff.booking_type,
        booking_status="DRAFT",
        base_price=tariff.base_price,
        included_helpers=tariff.included_helpers,
        extra_participant_price=tariff.extra_participant_price,
        notes=payload.notes,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(booking)
    db.flush()

    recalculate_booking(db, booking, user.id)

    audit(
        db,
        user_id=user.id,
        entity_type="BOOKING",
        entity_id=str(booking.id),
        action="CREATE",
        after=booking_dict(booking),
    )

    db.commit()

    loaded = booking_with_details(db, booking.id)
    return booking_dict(loaded, include_details=True)


@router.get("/bookings/{booking_id}")
def get_booking(
    booking_id: UUID,
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    booking = booking_with_details(db, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return booking_dict(booking, include_details=True)


@router.post("/bookings/{booking_id}/participants", status_code=201)
def add_booking_participant(
    booking_id: UUID,
    payload: BookingParticipantCreate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.booking_status not in ["DRAFT", "SUBMITTED"]:
        raise HTTPException(
            status_code=409,
            detail="Participants can only be changed in DRAFT or SUBMITTED booking",
        )

    if payload.role == "OWNER":
        existing_owner = db.scalar(
            select(BookingParticipant).where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.role == "OWNER",
                BookingParticipant.registration_status != "CANCELLED",
            )
        )
        if existing_owner:
            raise HTTPException(
                status_code=409,
                detail="Booking already has OWNER",
            )

    participant = Participant(
        code=next_code(db, "PRS"),
        last_name=payload.participant.last_name.strip(),
        first_name=payload.participant.first_name.strip(),
        middle_name=payload.participant.middle_name,
        nickname=payload.participant.nickname.strip(),
        email=(
            str(payload.participant.email).lower()
            if payload.participant.email
            else None
        ),
        phone=payload.participant.phone,
        telegram=payload.participant.telegram,
        birth_date=payload.participant.birth_date,
        notes=payload.participant.notes,
        active=True,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(participant)
    db.flush()

    max_sort = db.scalar(
        select(func.coalesce(func.max(BookingParticipant.sort_order), 0))
        .where(BookingParticipant.booking_id == booking.id)
    )

    link = BookingParticipant(
        code=next_code(db, "BPR"),
        booking_id=booking.id,
        participant_id=participant.id,
        role=payload.role,
        sort_order=int(max_sort or 0) + 1,
        registration_status="REGISTERED",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(link)
    db.flush()

    recalculate_booking(db, booking, user.id)

    audit(
        db,
        user_id=user.id,
        entity_type="PARTICIPANT",
        entity_id=str(participant.id),
        action="CREATE",
        after=participant_dict(participant),
        metadata={"booking_id": str(booking.id), "role": payload.role},
    )

    db.commit()

    loaded = booking_with_details(db, booking.id)
    return booking_dict(loaded, include_details=True)


@router.delete("/booking-participants/{link_id}", status_code=200)
def cancel_booking_participant(
    link_id: UUID,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    link = db.get(BookingParticipant, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Booking participant not found")

    booking = db.get(Booking, link.booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.booking_status not in ["DRAFT", "SUBMITTED"]:
        raise HTTPException(
            status_code=409,
            detail="Participants can only be changed in DRAFT or SUBMITTED booking",
        )

    link.registration_status = "CANCELLED"
    link.updated_by = user.id

    recalculate_booking(db, booking, user.id)

    audit(
        db,
        user_id=user.id,
        entity_type="PARTICIPANT",
        entity_id=str(link.participant_id),
        action="UPDATE",
        metadata={
            "booking_id": str(booking.id),
            "registration_status": "CANCELLED",
        },
    )

    db.commit()
    loaded = booking_with_details(db, booking.id)
    return booking_dict(loaded, include_details=True)


@router.patch("/participants/{participant_id}")
def update_participant(
    participant_id: UUID,
    payload: ParticipantUpdate,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    participant = db.get(Participant, participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    before = participant_dict(participant)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if field == "email" and value is not None:
            value = str(value).lower()
        setattr(participant, field, value)

    participant.updated_by = user.id
    db.flush()

    audit(
        db,
        user_id=user.id,
        entity_type="PARTICIPANT",
        entity_id=str(participant.id),
        action="UPDATE",
        before=before,
        after=participant_dict(participant),
    )

    db.commit()
    return participant_dict(participant)


@router.post("/bookings/{booking_id}/transition")
def change_booking_status(
    booking_id: UUID,
    payload: BookingTransition,
    _: CsrfDep,
    user: User = Depends(write_user()),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    before = booking_dict(booking)

    transition_booking(
        db,
        booking,
        payload.status,
        user.id,
        payload.comment,
    )

    audit(
        db,
        user_id=user.id,
        entity_type="BOOKING",
        entity_id=str(booking.id),
        action="UPDATE",
        before=before,
        after=booking_dict(booking),
        metadata={"transition": f"{before['booking_status']}->{payload.status}"},
    )

    db.commit()

    loaded = booking_with_details(db, booking.id)
    return booking_dict(loaded, include_details=True)


@router.get("/core/dashboard")
def core_dashboard(
    event_id: UUID | None = None,
    _: User = Depends(read_user()),
    db: Session = Depends(get_db),
):
    if event_id is None:
        event_id = current_event_id(db)

    if not event_id:
        return {
            "event": None,
            "vendors": 0,
            "bookings": 0,
            "participants": 0,
            "submitted": 0,
            "confirmed": 0,
            "total": money(0),
            "balance": money(0),
        }

    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    bookings = db.scalars(
        select(Booking).where(
            Booking.event_id == event_id,
            Booking.booking_status.notin_(["CANCELLED", "REJECTED"]),
        )
    ).all()

    booking_ids = [booking.id for booking in bookings]
    vendor_ids = {booking.vendor_id for booking in bookings}

    participants = 0
    if booking_ids:
        participants = db.scalar(
            select(func.count())
            .select_from(BookingParticipant)
            .where(
                BookingParticipant.booking_id.in_(booking_ids),
                BookingParticipant.registration_status != "CANCELLED",
            )
        )

    return {
        "event": event_dict(event),
        "vendors": len(vendor_ids),
        "bookings": len(bookings),
        "participants": int(participants or 0),
        "submitted": sum(1 for b in bookings if b.booking_status == "SUBMITTED"),
        "confirmed": sum(1 for b in bookings if b.booking_status == "CONFIRMED"),
        "total": money(sum((money(b.final_total) for b in bookings), money(0))),
        "balance": money(sum((money(b.balance) for b in bookings), money(0))),
    }
