from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class PublicVendorInput(BaseModel):
    vendor_name: str = Field(min_length=1, max_length=250)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=100)
    telegram: str | None = Field(default=None, max_length=150)
    website: str | None = Field(default=None, max_length=500)
    social_link: str | None = Field(default=None, max_length=500)
    description: str | None = None


class PublicPersonInput(BaseModel):
    last_name: str = Field(min_length=1, max_length=150)
    first_name: str = Field(min_length=1, max_length=150)
    middle_name: str | None = Field(default=None, max_length=150)
    nickname: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=100)
    telegram: str | None = Field(default=None, max_length=150)


class PublicApplicationCreate(BaseModel):
    event_id: UUID | None = None
    booking_type: str = Field(pattern="^(FULL|HALF)$")
    vendor: PublicVendorInput
    owner: PublicPersonInput
    helpers: list[PublicPersonInput] = Field(default_factory=list, max_length=20)
    notes: str | None = None
    confirmed: bool = False
    company_fax: str | None = None

    @model_validator(mode="after")
    def validate_confirmed(self):
        if not self.confirmed:
            raise ValueError("Data confirmation is required")
        return self


class ReviewAction(BaseModel):
    comment: str | None = None


class RejectAction(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class PaymentCreate(BaseModel):
    payment_type: str = Field(default="PAYMENT", pattern="^(PAYMENT|REFUND)$")
    amount: Decimal = Field(gt=0)
    payment_method: str = Field(
        pattern="^(CASH|CARD|TRANSFER|SBP|OTHER)$"
    )
    reference: str | None = Field(default=None, max_length=250)
    client_operation_id: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class AdjustmentCreate(BaseModel):
    charge_type: str = Field(
        pattern="^(DISCOUNT|SURCHARGE|MANUAL)$"
    )
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal
    notes: str | None = None

    @model_validator(mode="after")
    def validate_amount(self):
        if self.amount == 0:
            raise ValueError("Adjustment amount cannot be zero")
        return self
