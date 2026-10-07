from uuid import UUID

from pydantic import BaseModel, Field


class BookingAdminUpdate(BaseModel):
    vendor_id: UUID | None = None
    tariff_id: UUID | None = None
    notes: str | None = None


class AssignmentAdminUpdate(BaseModel):
    booking_id: UUID
    table_id: UUID
    start_slot: int = Field(default=1, ge=1, le=2)


class PaymentCancelInput(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ChargeDeactivateInput(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
