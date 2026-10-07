from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class EventCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=250)
    start_date: date
    end_date: date
    venue: str | None = Field(default=None, max_length=250)
    city: str | None = Field(default=None, max_length=150)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    status: str = Field(
        default="DRAFT",
        pattern="^(DRAFT|REGISTRATION|ACTIVE|CLOSED|ARCHIVED)$",
    )
    registration_open: bool = False
    vendor_checkin_open: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self


class EventUpdate(BaseModel):
    event_name: str | None = Field(default=None, min_length=1, max_length=250)
    start_date: date | None = None
    end_date: date | None = None
    venue: str | None = Field(default=None, max_length=250)
    city: str | None = Field(default=None, max_length=150)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    status: str | None = Field(
        default=None,
        pattern="^(DRAFT|REGISTRATION|ACTIVE|CLOSED|ARCHIVED)$",
    )
    registration_open: bool | None = None
    vendor_checkin_open: bool | None = None
    notes: str | None = None


class TariffCreate(BaseModel):
    tariff_name: str = Field(min_length=1, max_length=250)
    booking_type: str = Field(pattern="^(FULL|HALF)$")
    base_price: Decimal = Field(ge=0)
    included_helpers: int = Field(ge=0, le=100)
    extra_participant_price: Decimal = Field(ge=0)
    valid_from: date
    valid_to: date | None = None
    active: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be >= valid_from")
        return self


class TariffUpdate(BaseModel):
    tariff_name: str | None = Field(default=None, min_length=1, max_length=250)
    booking_type: str | None = Field(default=None, pattern="^(FULL|HALF)$")
    base_price: Decimal | None = Field(default=None, ge=0)
    included_helpers: int | None = Field(default=None, ge=0, le=100)
    extra_participant_price: Decimal | None = Field(default=None, ge=0)
    valid_from: date | None = None
    valid_to: date | None = None
    active: bool | None = None
    notes: str | None = None


class VendorCreate(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=250)
    legal_name: str | None = Field(default=None, max_length=250)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=100)
    telegram: str | None = Field(default=None, max_length=150)
    website: str | None = Field(default=None, max_length=500)
    social_link: str | None = Field(default=None, max_length=500)
    description: str | None = None
    notes: str | None = None
    active: bool = True


class VendorUpdate(BaseModel):
    vendor_name: str | None = Field(default=None, min_length=1, max_length=250)
    legal_name: str | None = Field(default=None, max_length=250)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=100)
    telegram: str | None = Field(default=None, max_length=150)
    website: str | None = Field(default=None, max_length=500)
    social_link: str | None = Field(default=None, max_length=500)
    description: str | None = None
    notes: str | None = None
    active: bool | None = None


class BookingCreate(BaseModel):
    event_id: UUID
    vendor_id: UUID
    tariff_id: UUID
    notes: str | None = None


class BookingTransition(BaseModel):
    status: str = Field(
        pattern="^(DRAFT|SUBMITTED|APPROVED|AWAITING_PAYMENT|CONFIRMED|CANCELLED|REJECTED)$"
    )
    comment: str | None = None


class ParticipantCreate(BaseModel):
    last_name: str = Field(min_length=1, max_length=150)
    first_name: str = Field(min_length=1, max_length=150)
    middle_name: str | None = Field(default=None, max_length=150)
    nickname: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=100)
    telegram: str | None = Field(default=None, max_length=150)
    birth_date: date | None = None
    notes: str | None = None


class ParticipantUpdate(BaseModel):
    last_name: str | None = Field(default=None, min_length=1, max_length=150)
    first_name: str | None = Field(default=None, min_length=1, max_length=150)
    middle_name: str | None = Field(default=None, max_length=150)
    nickname: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=100)
    telegram: str | None = Field(default=None, max_length=150)
    birth_date: date | None = None
    notes: str | None = None
    active: bool | None = None


class BookingParticipantCreate(BaseModel):
    role: str = Field(pattern="^(OWNER|HELPER)$")
    participant: ParticipantCreate
