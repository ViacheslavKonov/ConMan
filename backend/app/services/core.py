from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.core import (
    AppSetting,
    Booking,
    BookingParticipant,
    Charge,
    Event,
    Participant,
    Payment,
    Tariff,
    Vendor,
)
from app.services.codes import next_code


ZERO = Decimal("0.00")


def money(value) -> Decimal:
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(Decimal("0.01"))


def current_event_id(db: Session) -> UUID | None:
    setting = db.get(AppSetting, "current_event_id")
    if not setting or not setting.value:
        return None
    try:
        return UUID(setting.value)
    except ValueError:
        return None


def set_current_event(db: Session, event_id: UUID) -> Event:
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    setting = db.get(AppSetting, "current_event_id")
    if setting is None:
        setting = AppSetting(
            key="current_event_id",
            value=str(event.id),
        )
        db.add(setting)
    else:
        setting.value = str(event.id)

    db.flush()
    return event


def get_current_event(db: Session) -> Event | None:
    event_id = current_event_id(db)
    return db.get(Event, event_id) if event_id else None


def find_applicable_tariff(
    db: Session,
    event_id: UUID,
    booking_type: str,
    on_date,
) -> Tariff | None:
    return db.scalar(
        select(Tariff)
        .where(
            Tariff.event_id == event_id,
            Tariff.booking_type == booking_type,
            Tariff.active.is_(True),
            Tariff.valid_from <= on_date,
            (Tariff.valid_to.is_(None) | (Tariff.valid_to >= on_date)),
        )
        .order_by(Tariff.valid_from.desc(), Tariff.created_at.desc())
        .limit(1)
    )


def recalculate_booking(
    db: Session,
    booking: Booking,
    actor_id: UUID | None = None,
) -> Booking:
    links = db.scalars(
        select(BookingParticipant)
        .where(
            BookingParticipant.booking_id == booking.id,
            BookingParticipant.registration_status != "CANCELLED",
        )
        .options(selectinload(BookingParticipant.participant))
    ).all()

    links = sorted(
        links,
        key=lambda link: (
            0 if link.role == "OWNER" else 1,
            link.sort_order,
            str(link.id),
        ),
    )

    capacity = 1 + int(booking.included_helpers or 0)
    extra_price = money(booking.extra_participant_price)

    for index, link in enumerate(links):
        included = index < capacity
        link.is_included = included
        link.charge_amount = ZERO if included else extra_price
        link.updated_by = actor_id

    participants_count = len(links)
    included_count = min(participants_count, capacity)
    extra_count = max(participants_count - capacity, 0)
    extras_amount = money(extra_price * extra_count)

    db.execute(
        update(Charge)
        .where(
            Charge.booking_id == booking.id,
            Charge.automatic.is_(True),
            Charge.active.is_(True),
            Charge.charge_type.in_(["TABLE", "EXTRA_PARTICIPANT"]),
        )
        .values(active=False)
    )

    base_price = money(booking.base_price)

    db.add(
        Charge(
            code=next_code(db, "CHG"),
            booking_id=booking.id,
            event_id=booking.event_id,
            charge_type="TABLE",
            description=f"{booking.booking_type} table",
            quantity=Decimal("1"),
            unit_price=base_price,
            amount=base_price,
            automatic=True,
            source_id=str(booking.tariff_id),
            active=True,
            created_by=actor_id,
        )
    )

    if extra_count > 0:
        db.add(
            Charge(
                code=next_code(db, "CHG"),
                booking_id=booking.id,
                event_id=booking.event_id,
                charge_type="EXTRA_PARTICIPANT",
                description="Extra participants",
                quantity=Decimal(extra_count),
                unit_price=extra_price,
                amount=extras_amount,
                automatic=True,
                source_id=str(booking.id),
                active=True,
                created_by=actor_id,
            )
        )

    db.flush()

    total = db.scalar(
        select(func.coalesce(func.sum(Charge.amount), 0))
        .where(
            Charge.booking_id == booking.id,
            Charge.active.is_(True),
        )
    )

    final_total = money(total)

    payment_rows = db.scalars(
        select(Payment).where(
            Payment.booking_id == booking.id,
            Payment.status == "CONFIRMED",
        )
    ).all()

    paid_amount = money(
        sum(
            (
                money(item.amount)
                if item.payment_type == "PAYMENT"
                else -money(item.amount)
            )
            for item in payment_rows
        ) if payment_rows else ZERO
    )
    balance = money(final_total - paid_amount)

    if final_total == ZERO:
        payment_status = "NO_PAYMENT_REQUIRED"
    elif paid_amount <= ZERO:
        payment_status = "UNPAID"
    elif paid_amount < final_total:
        payment_status = "PARTIAL"
    elif paid_amount == final_total:
        payment_status = "PAID"
    else:
        payment_status = "OVERPAID"

    booking.participants_count = participants_count
    booking.included_participants_count = included_count
    booking.extra_participants_count = extra_count
    booking.extras_amount = extras_amount
    booking.calculated_total = final_total
    booking.final_total = final_total
    booking.paid_amount = paid_amount
    booking.balance = balance
    booking.payment_status = payment_status
    booking.updated_by = actor_id

    db.flush()
    return booking


ALLOWED_TRANSITIONS = {
    "DRAFT": {"SUBMITTED", "CANCELLED"},
    "SUBMITTED": {"APPROVED", "REJECTED", "CANCELLED"},
    "APPROVED": {"AWAITING_PAYMENT", "CONFIRMED", "CANCELLED"},
    "AWAITING_PAYMENT": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"CANCELLED"},
    "CANCELLED": set(),
    "REJECTED": set(),
}


def transition_booking(
    db: Session,
    booking: Booking,
    target_status: str,
    actor_id: UUID,
    comment: str | None = None,
) -> Booking:
    current = booking.booking_status

    if target_status == current:
        return booking

    if target_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transition {current} -> {target_status} is not allowed",
        )

    if target_status == "SUBMITTED":
        owners = db.scalar(
            select(func.count())
            .select_from(BookingParticipant)
            .where(
                BookingParticipant.booking_id == booking.id,
                BookingParticipant.role == "OWNER",
                BookingParticipant.registration_status != "CANCELLED",
            )
        )
        if owners != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="SUBMITTED booking must have exactly one OWNER",
            )

    if target_status == "CONFIRMED" and money(booking.balance) > ZERO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Booking cannot be CONFIRMED while balance is positive",
        )

    booking.booking_status = target_status
    booking.updated_by = actor_id

    if target_status == "APPROVED":
        booking.approved_date = datetime.now(UTC)

    if comment:
        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        line = f"[{stamp}] {current} -> {target_status}: {comment.strip()}"
        booking.notes = f"{booking.notes}\n{line}".strip() if booking.notes else line

    db.flush()
    return booking


def booking_with_details(db: Session, booking_id: UUID) -> Booking | None:
    return db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .options(
            selectinload(Booking.vendor),
            selectinload(Booking.tariff),
            selectinload(Booking.participant_links)
            .selectinload(BookingParticipant.participant),
            selectinload(Booking.charges),
            selectinload(Booking.payments),
        )
    )


def booking_dict(booking: Booking, include_details: bool = False) -> dict:
    data = {
        "id": str(booking.id),
        "code": booking.code,
        "event_id": str(booking.event_id),
        "vendor_id": str(booking.vendor_id),
        "tariff_id": str(booking.tariff_id),
        "booking_type": booking.booking_type,
        "booking_status": booking.booking_status,
        "application_date": booking.application_date,
        "approved_date": booking.approved_date,
        "base_price": money(booking.base_price),
        "included_helpers": booking.included_helpers,
        "extra_participant_price": money(booking.extra_participant_price),
        "participants_count": booking.participants_count,
        "included_participants_count": booking.included_participants_count,
        "extra_participants_count": booking.extra_participants_count,
        "extras_amount": money(booking.extras_amount),
        "final_total": money(booking.final_total),
        "paid_amount": money(booking.paid_amount),
        "balance": money(booking.balance),
        "payment_status": booking.payment_status,
        "seating_status": booking.seating_status,
        "checkin_status": booking.checkin_status,
        "notes": booking.notes,
    }

    if include_details:
        data["vendor"] = vendor_dict(booking.vendor) if booking.vendor else None
        data["tariff"] = tariff_dict(booking.tariff) if booking.tariff else None
        data["participants"] = [
            booking_participant_dict(link)
            for link in sorted(
                booking.participant_links,
                key=lambda x: (x.sort_order, str(x.id)),
            )
            if link.registration_status != "CANCELLED"
        ]
        data["charges"] = [
            {
                "id": str(charge.id),
                "code": charge.code,
                "charge_type": charge.charge_type,
                "description": charge.description,
                "quantity": money(charge.quantity),
                "unit_price": money(charge.unit_price),
                "amount": money(charge.amount),
                "automatic": charge.automatic,
                "active": charge.active,
            }
            for charge in booking.charges
            if charge.active
        ]

        data["payments"] = [
            payment_dict(payment)
            for payment in sorted(
                booking.payments,
                key=lambda item: (item.payment_date, str(item.id)),
                reverse=True,
            )
        ]

    return data


def payment_dict(payment: Payment) -> dict:
    return {
        "id": str(payment.id),
        "code": payment.code,
        "booking_id": str(payment.booking_id),
        "event_id": str(payment.event_id),
        "payment_type": payment.payment_type,
        "payment_date": payment.payment_date,
        "amount": money(payment.amount),
        "payment_method": payment.payment_method,
        "reference": payment.reference,
        "client_operation_id": payment.client_operation_id,
        "status": payment.status,
        "notes": payment.notes,
    }


def event_dict(event: Event) -> dict:
    return {
        "id": str(event.id),
        "code": event.code,
        "event_name": event.event_name,
        "start_date": event.start_date,
        "end_date": event.end_date,
        "venue": event.venue,
        "city": event.city,
        "currency": event.currency,
        "status": event.status,
        "registration_open": event.registration_open,
        "vendor_checkin_open": event.vendor_checkin_open,
        "seating_preferences_open": event.seating_preferences_open,
        "notes": event.notes,
    }


def vendor_dict(vendor: Vendor) -> dict:
    return {
        "id": str(vendor.id),
        "code": vendor.code,
        "vendor_name": vendor.vendor_name,
        "legal_name": vendor.legal_name,
        "email": vendor.email,
        "phone": vendor.phone,
        "telegram": vendor.telegram,
        "website": vendor.website,
        "social_link": vendor.social_link,
        "description": vendor.description,
        "notes": vendor.notes,
        "active": vendor.active,
    }


def tariff_dict(tariff: Tariff) -> dict:
    return {
        "id": str(tariff.id),
        "code": tariff.code,
        "event_id": str(tariff.event_id),
        "tariff_name": tariff.tariff_name,
        "booking_type": tariff.booking_type,
        "base_price": money(tariff.base_price),
        "included_helpers": tariff.included_helpers,
        "included_participants": tariff.included_helpers + 1,
        "extra_participant_price": money(tariff.extra_participant_price),
        "valid_from": tariff.valid_from,
        "valid_to": tariff.valid_to,
        "active": tariff.active,
        "notes": tariff.notes,
    }


def participant_dict(participant: Participant) -> dict:
    return {
        "id": str(participant.id),
        "code": participant.code,
        "last_name": participant.last_name,
        "first_name": participant.first_name,
        "middle_name": participant.middle_name,
        "nickname": participant.nickname,
        "email": participant.email,
        "phone": participant.phone,
        "telegram": participant.telegram,
        "birth_date": participant.birth_date,
        "notes": participant.notes,
        "active": participant.active,
    }


def booking_participant_dict(link: BookingParticipant) -> dict:
    return {
        "id": str(link.id),
        "code": link.code,
        "booking_id": str(link.booking_id),
        "participant_id": str(link.participant_id),
        "role": link.role,
        "sort_order": link.sort_order,
        "is_included": link.is_included,
        "charge_amount": money(link.charge_amount),
        "registration_status": link.registration_status,
        "checkin_status": link.checkin_status,
        "badge_required": link.badge_required,
        "badge_issued": link.badge_issued,
        "participant": participant_dict(link.participant) if link.participant else None,
    }
