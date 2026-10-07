from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.models.core import (
    Booking,
    BookingParticipant,
    Event,
    Participant,
    Vendor,
)
from app.schemas.step3 import PublicApplicationCreate, PublicPersonInput
from app.schemas.step7 import PreferenceAccessInput, PublicPreferenceUpdate
from app.services.codes import next_code
from app.services.planning import (
    public_preference_access,
    public_preference_payload,
    save_public_preference,
)
from app.services.core import (
    booking_dict,
    booking_with_details,
    event_dict,
    find_applicable_tariff,
    get_current_event,
    recalculate_booking,
    tariff_dict,
    transition_booking,
)


router = APIRouter(prefix="/public", tags=["public"])


@router.get("/registration")
def registration_config(
    event_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
):
    open_events = list(
        db.scalars(
            select(Event)
            .where(Event.registration_open.is_(True))
            .order_by(Event.start_date, Event.event_name)
        ).all()
    )

    event = None
    if event_id is not None:
        event = db.get(Event, event_id)
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Registration event not found",
            )
    else:
        current = get_current_event(db)
        if current is not None and current.registration_open:
            event = current
        elif open_events:
            event = open_events[0]
        elif current is not None:
            event = current

    event_options = list(open_events)
    if event is not None and all(item.id != event.id for item in event_options):
        event_options.insert(0, event)

    tariffs = {}
    today = date.today()

    if event is not None:
        for booking_type in ("FULL", "HALF"):
            tariff = find_applicable_tariff(
                db,
                event.id,
                booking_type,
                today,
            )
            if tariff:
                tariffs[booking_type] = tariff_dict(tariff)

    if event is None:
        available = False
        reason = "NO_EVENT"
        message = "Нет мероприятий с открытой регистрацией."
    elif not event.registration_open:
        available = False
        reason = "REGISTRATION_CLOSED"
        message = "Регистрация вендоров для этого мероприятия закрыта."
    elif not tariffs:
        available = False
        reason = "NO_ACTIVE_TARIFFS"
        message = "Для этого мероприятия нет действующего тарифа FULL или HALF."
    else:
        available = True
        reason = "OK"
        message = ""

    return {
        "available": available,
        "reason": reason,
        "message": message,
        "event": event_dict(event) if event is not None else None,
        "events": [event_dict(item) for item in event_options],
        "tariffs": tariffs,
    }


@router.post("/preferences/access")
def access_seating_preferences(
    payload: PreferenceAccessInput,
    db: Session = Depends(get_db),
):
    return public_preference_access(
        db,
        payload.booking_code,
        str(payload.email),
    )


@router.get("/preferences/{token}")
def read_seating_preferences(
    token: str,
    db: Session = Depends(get_db),
):
    return public_preference_payload(
        db,
        token,
    )


@router.put("/preferences/{token}")
def update_seating_preferences(
    token: str,
    payload: PublicPreferenceUpdate,
    db: Session = Depends(get_db),
):
    return save_public_preference(
        db,
        token,
        payload,
    )


@router.post("/applications", status_code=201)
def submit_public_application(
    payload: PublicApplicationCreate,
    db: Session = Depends(get_db),
):
    if payload.company_fax and payload.company_fax.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application rejected",
        )

    event = (
        db.get(Event, payload.event_id)
        if payload.event_id is not None
        else get_current_event(db)
    )
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration event is not configured",
        )

    if not event.registration_open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Registration is closed",
        )

    tariff = find_applicable_tariff(
        db,
        event.id,
        payload.booking_type,
        date.today(),
    )
    if tariff is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No active {payload.booking_type} tariff",
        )

    normalized_email = str(payload.vendor.email).strip().lower()

    vendor = db.scalar(
        select(Vendor).where(
            func.lower(Vendor.email) == normalized_email,
            Vendor.active.is_(True),
        )
    )

    if vendor is not None:
        duplicate = db.scalar(
            select(Booking).where(
                Booking.event_id == event.id,
                Booking.vendor_id == vendor.id,
                Booking.booking_status.notin_(["CANCELLED", "REJECTED"]),
            )
        )

        if duplicate is not None:
            existing = booking_with_details(db, duplicate.id)
            return {
                "duplicate": True,
                "application": public_application_result(existing),
            }

    if vendor is None:
        vendor = Vendor(
            code=next_code(db, "VND"),
            vendor_name=payload.vendor.vendor_name.strip(),
            email=normalized_email,
            phone=payload.vendor.phone,
            telegram=payload.vendor.telegram,
            website=payload.vendor.website,
            social_link=payload.vendor.social_link,
            description=payload.vendor.description,
            active=True,
        )
        db.add(vendor)
        db.flush()

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
        pricing_locked=True,
        notes=public_notes(payload.notes),
    )
    db.add(booking)
    db.flush()

    people = [
        ("OWNER", payload.owner),
        *[("HELPER", helper) for helper in payload.helpers],
    ]

    for index, (role, person_input) in enumerate(people, start=1):
        person = create_public_person(
            db,
            person_input,
            fallback_email=(
                normalized_email
                if role == "OWNER"
                else None
            ),
        )

        db.add(
            BookingParticipant(
                code=next_code(db, "BPR"),
                booking_id=booking.id,
                participant_id=person.id,
                role=role,
                sort_order=index,
                registration_status="REGISTERED",
                badge_required=True,
            )
        )

    db.flush()

    recalculate_booking(db, booking)
    transition_booking(
        db,
        booking,
        "SUBMITTED",
        actor_id=None,
        comment="Public registration",
    )

    audit(
        db,
        user_id=None,
        entity_type="BOOKING",
        entity_id=str(booking.id),
        action="CREATE",
        after={
            "code": booking.code,
            "source": "PUBLIC_REGISTRATION",
            "vendor_id": str(vendor.id),
            "booking_type": booking.booking_type,
        },
    )

    db.commit()

    loaded = booking_with_details(db, booking.id)

    return {
        "duplicate": False,
        "application": public_application_result(loaded),
    }


def create_public_person(
    db: Session,
    person: PublicPersonInput,
    fallback_email: str | None,
) -> Participant:
    email = (
        str(person.email).lower()
        if person.email
        else fallback_email
    )

    participant = Participant(
        code=next_code(db, "PRS"),
        last_name=person.last_name.strip(),
        first_name=person.first_name.strip(),
        middle_name=person.middle_name,
        nickname=person.nickname.strip(),
        email=email,
        phone=person.phone,
        telegram=person.telegram,
        active=True,
    )
    db.add(participant)
    db.flush()
    return participant


def public_notes(notes: str | None) -> str:
    prefix = "Публичная регистрация."
    value = (notes or "").strip()
    return f"{prefix}\n{value}" if value else prefix


def public_application_result(booking: Booking) -> dict:
    data = booking_dict(booking, include_details=True)
    return {
        "booking_id": data["id"],
        "booking_code": data["code"],
        "booking_status": data["booking_status"],
        "booking_type": data["booking_type"],
        "vendor_name": (
            data["vendor"]["vendor_name"]
            if data.get("vendor")
            else ""
        ),
        "participants_count": data["participants_count"],
        "included_participants_count": data["included_participants_count"],
        "extra_participants_count": data["extra_participants_count"],
        "extras_amount": data["extras_amount"],
        "final_total": data["final_total"],
        "payment_status": data["payment_status"],
    }
