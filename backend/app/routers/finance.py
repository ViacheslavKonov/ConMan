from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.dependencies import CsrfDep, require_roles
from app.models.core import Booking, Charge, Payment
from app.models.user import User, UserRole
from app.schemas.step3 import AdjustmentCreate, PaymentCreate
from app.services.codes import next_code
from app.services.core import (
    booking_dict,
    booking_with_details,
    money,
    recalculate_booking,
)


router = APIRouter(tags=["finance"])

FINANCE_ROLES = [
    UserRole.ADMIN.value,
    UserRole.MANAGER.value,
    UserRole.REGISTRATION.value,
]


def finance_user():
    return require_roles(*FINANCE_ROLES)


@router.post("/bookings/{booking_id}/payments", status_code=201)
def record_payment(
    booking_id: UUID,
    payload: PaymentCreate,
    _: CsrfDep,
    user: User = Depends(finance_user()),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if payload.client_operation_id:
        existing = db.scalar(
            select(Payment).where(
                Payment.client_operation_id == payload.client_operation_id
            )
        )
        if existing:
            loaded = booking_with_details(db, existing.booking_id)
            return {
                "duplicate": True,
                "booking": booking_dict(loaded, include_details=True),
            }

    amount = money(payload.amount)

    if payload.payment_type == "PAYMENT":
        if booking.booking_status in ["CANCELLED", "REJECTED"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot accept payment for cancelled/rejected booking",
            )

        if money(booking.balance) <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Booking has no outstanding balance",
            )

        if amount > money(booking.balance):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment exceeds outstanding balance",
            )

    if payload.payment_type == "REFUND":
        if money(booking.paid_amount) <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nothing to refund",
            )

        if amount > money(booking.paid_amount):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refund exceeds paid amount",
            )

    payment = Payment(
        code=next_code(db, "PAY"),
        booking_id=booking.id,
        event_id=booking.event_id,
        payment_type=payload.payment_type,
        amount=amount,
        payment_method=payload.payment_method,
        reference=payload.reference,
        client_operation_id=payload.client_operation_id,
        status="CONFIRMED",
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(payment)
    db.flush()

    recalculate_booking(db, booking, user.id)

    audit(
        db,
        user_id=user.id,
        entity_type="PAYMENT",
        entity_id=str(payment.id),
        action="CREATE",
        after={
            "code": payment.code,
            "booking_id": str(booking.id),
            "payment_type": payment.payment_type,
            "amount": str(payment.amount),
            "payment_method": payment.payment_method,
        },
    )

    db.commit()

    loaded = booking_with_details(db, booking.id)
    return {
        "duplicate": False,
        "booking": booking_dict(loaded, include_details=True),
    }


@router.post("/bookings/{booking_id}/adjustments", status_code=201)
def create_adjustment(
    booking_id: UUID,
    payload: AdjustmentCreate,
    _: CsrfDep,
    user: User = Depends(
        require_roles(
            UserRole.ADMIN.value,
            UserRole.MANAGER.value,
        )
    ),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    raw = money(payload.amount)

    if payload.charge_type == "DISCOUNT":
        amount = -abs(raw)
    elif payload.charge_type == "SURCHARGE":
        amount = abs(raw)
    else:
        amount = raw

    charge = Charge(
        code=next_code(db, "CHG"),
        booking_id=booking.id,
        event_id=booking.event_id,
        charge_type=payload.charge_type,
        description=payload.description.strip(),
        quantity=1,
        unit_price=amount,
        amount=amount,
        automatic=False,
        source_id=None,
        active=True,
        created_by=user.id,
    )
    db.add(charge)
    db.flush()

    recalculate_booking(db, booking, user.id)

    audit(
        db,
        user_id=user.id,
        entity_type="BOOKING",
        entity_id=str(booking.id),
        action="UPDATE",
        after={
            "adjustment_code": charge.code,
            "charge_type": charge.charge_type,
            "amount": str(charge.amount),
            "description": charge.description,
        },
    )

    db.commit()

    loaded = booking_with_details(db, booking.id)
    return booking_dict(loaded, include_details=True)
