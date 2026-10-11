"""Schema for the bundled synthetic dataset, independent of database IDs."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.core import EventCreate, ParticipantCreate, TariffCreate, VendorCreate
from app.schemas.step3 import PaymentCreate
from app.schemas.step4 import LayoutZoneCreate


Code = Annotated[str, Field(pattern=r"^DEMO-[A-Z0-9-]+$", max_length=32)]
ELIGIBLE = {"APPROVED", "AWAITING_PAYMENT", "CONFIRMED"}


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: Code


class DemoEvent(EventCreate, Record):
    pass


class DemoTariff(TariffCreate, Record):
    event: Code


class DemoVendor(VendorCreate, Record):
    pass


class DemoParticipant(ParticipantCreate, Record):
    pass


class DemoZone(LayoutZoneCreate, Record):
    event: Code
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class DemoTable(Record):
    event: Code
    zone: Code
    table_number: int = Field(ge=1)
    table_label: str = Field(min_length=1, max_length=50)
    capacity_slots: int = Field(default=2, ge=1, le=2)
    x: int
    y: int
    width: int = Field(default=120, ge=60, le=300)
    height: int = Field(default=54, ge=30, le=200)
    sort_order: int = 0


class DemoLink(Record):
    participant: Code
    role: Literal["OWNER", "HELPER"]
    checked_in: bool = False
    badge_number: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_badge(self):
        if self.badge_number and not self.checked_in:
            raise ValueError("A badge requires check-in")
        return self


class DemoPayment(PaymentCreate, Record):
    payment_date: datetime
    status: Literal["CONFIRMED", "CANCELLED"] = "CONFIRMED"

    @model_validator(mode="after")
    def validate_timestamp(self):
        if self.payment_date.tzinfo is None:
            raise ValueError("Payment timestamp must include a timezone")
        return self


class DemoAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: Code
    start_slot: int = Field(default=1, ge=1, le=2)


class DemoPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["DRAFT", "SUBMITTED"] = "DRAFT"
    table: Code
    zone: Code
    near: Code | None = None
    avoid: Code | None = None


class DemoBooking(Record):
    event: Code
    vendor: Code
    tariff: Code
    status: Literal[
        "DRAFT", "SUBMITTED", "APPROVED", "AWAITING_PAYMENT",
        "CONFIRMED", "CANCELLED", "REJECTED",
    ]
    application_date: datetime
    notes: str
    participants: list[DemoLink] = Field(min_length=1)
    payments: list[DemoPayment] = Field(default_factory=list)
    assignment: DemoAssignment | None = None
    preference: DemoPreference | None = None


class DemoDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: Literal["conman-demo-v1"]
    version: Literal[1]
    description: str
    primary_event: Code
    events: list[DemoEvent] = Field(min_length=1)
    tariffs: list[DemoTariff]
    vendors: list[DemoVendor]
    participants: list[DemoParticipant]
    zones: list[DemoZone]
    tables: list[DemoTable]
    bookings: list[DemoBooking]

    @model_validator(mode="after")
    def validate_graph(self):
        collections = {
            name: {item.code: item for item in getattr(self, name)}
            for name in ("events", "tariffs", "vendors", "participants", "zones", "tables", "bookings")
        }
        codes: set[str] = set()
        for name, items in collections.items():
            if len(items) != len(getattr(self, name)) or codes.intersection(items):
                raise ValueError(f"Duplicate codes in {name}")
            codes.update(items)

        def reference(name, code):
            if code not in collections[name]:
                raise ValueError(f"Unknown {name} reference: {code}")
            return collections[name][code]

        reference("events", self.primary_event)
        for item in [*self.tariffs, *self.zones, *self.tables]:
            reference("events", item.event)
        for table in self.tables:
            if reference("zones", table.zone).event != table.event:
                raise ValueError("Table and zone must belong to the same event")
        occupied: set[tuple[str, int]] = set()
        event_vendors: set[tuple[str, str]] = set()
        badges: set[str] = set()
        for booking in self.bookings:
            reference("events", booking.event)
            reference("vendors", booking.vendor)
            tariff = reference("tariffs", booking.tariff)
            if tariff.event != booking.event:
                raise ValueError("Booking tariff belongs to another event")
            if booking.application_date.tzinfo is None:
                raise ValueError("Application timestamp must include a timezone")
            on_date = booking.application_date.date()
            if on_date < tariff.valid_from or (tariff.valid_to and on_date > tariff.valid_to):
                raise ValueError("Tariff is not valid on the application date")
            pair = (booking.event, booking.vendor)
            if pair in event_vendors:
                raise ValueError("Duplicate vendor booking for an event")
            event_vendors.add(pair)
            if sum(link.role == "OWNER" for link in booking.participants) != 1:
                raise ValueError("Each booking must have exactly one OWNER")
            if len({link.participant for link in booking.participants}) != len(booking.participants):
                raise ValueError("Duplicate participant in a booking")
            for item in [*booking.participants, *booking.payments]:
                if item.code in codes:
                    raise ValueError(f"Duplicate code: {item.code}")
                codes.add(item.code)
            for link in booking.participants:
                reference("participants", link.participant)
                if link.checked_in and booking.status not in ELIGIBLE:
                    raise ValueError("Only eligible bookings can be checked in")
                if link.badge_number:
                    if link.badge_number in badges:
                        raise ValueError("Duplicate badge number")
                    badges.add(link.badge_number)
            total = tariff.base_price + max(0, len(booking.participants) - 1 - tariff.included_helpers) * tariff.extra_participant_price
            paid = sum((payment.amount if payment.payment_type == "PAYMENT" else -payment.amount
                        for payment in booking.payments if payment.status == "CONFIRMED"), Decimal("0"))
            if booking.status == "CONFIRMED" and paid < total:
                raise ValueError("Confirmed booking must not have a debt")
            if booking.assignment:
                table = reference("tables", booking.assignment.table)
                count = 2 if tariff.booking_type == "FULL" else 1
                slots = {(table.code, slot) for slot in range(
                    booking.assignment.start_slot, booking.assignment.start_slot + count,
                )}
                if (table.event != booking.event or booking.status not in ELIGIBLE
                        or max(slot for _, slot in slots) > table.capacity_slots
                        or occupied.intersection(slots)):
                    raise ValueError("Invalid or overlapping table assignment")
                occupied.update(slots)
            if booking.preference:
                pref = booking.preference
                if booking.status not in ELIGIBLE:
                    raise ValueError("Only eligible bookings can have preferences")
                if (reference("tables", pref.table).event != booking.event
                        or reference("zones", pref.zone).event != booking.event):
                    raise ValueError("Preference belongs to another event")
                for target in (pref.near, pref.avoid):
                    if target:
                        other = reference("bookings", target)
                        if other.code == booking.code or other.event != booking.event or other.status not in ELIGIBLE:
                            raise ValueError("Invalid adjacency preference")
        return self
