from pydantic import BaseModel, Field


class LayoutZoneCreate(BaseModel):
    zone_name: str = Field(min_length=1, max_length=250)
    zone_type: str = Field(default="GENERAL", max_length=32)
    color: str | None = Field(default="#B9C4FF", max_length=20)
    x: int = 0
    y: int = 0
    width: int = 280
    height: int = 160
    sort_order: int = 0
    notes: str | None = None


class LayoutZoneUpdate(BaseModel):
    zone_name: str | None = Field(default=None, min_length=1, max_length=250)
    zone_type: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=20)
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None
    sort_order: int | None = None
    active: bool | None = None
    notes: str | None = None


class BulkTableCreate(BaseModel):
    zone_id: str | None = None
    start_number: int = Field(ge=1)
    count: int = Field(ge=1, le=500)
    columns: int = Field(default=8, ge=1, le=20)
    start_x: int = 20
    start_y: int = 20
    x_gap: int = 12
    y_gap: int = 12
    width: int = Field(default=120, ge=60, le=300)
    height: int = Field(default=54, ge=30, le=200)
    capacity_slots: int = Field(default=2, ge=1, le=2)
    numbering_prefix: str | None = Field(default=None, max_length=20)


class LayoutTableUpdate(BaseModel):
    zone_id: str | None = None
    table_label: str | None = Field(default=None, max_length=50)
    capacity_slots: int | None = Field(default=None, ge=1, le=2)
    x: int | None = None
    y: int | None = None
    width: int | None = Field(default=None, ge=60, le=300)
    height: int | None = Field(default=None, ge=30, le=200)
    sort_order: int | None = None
    active: bool | None = None
    notes: str | None = None


class AssignBookingInput(BaseModel):
    booking_id: str
    table_id: str
    start_slot: int = Field(default=1, ge=1, le=2)


class UnassignBookingInput(BaseModel):
    booking_id: str
