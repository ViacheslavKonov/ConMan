from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class PreferenceAccessInput(BaseModel):
    booking_code: str = Field(min_length=1, max_length=32)
    email: EmailStr


class WeightedTablePreferenceInput(BaseModel):
    table_id: UUID
    priority: int = Field(default=3, ge=1, le=5)


class WeightedZonePreferenceInput(BaseModel):
    zone_id: UUID
    priority: int = Field(default=3, ge=1, le=5)


class AdjacencyPreferenceInput(BaseModel):
    target_booking_id: UUID
    preference_type: str = Field(
        pattern="^(MUST_NEAR|PREFER_NEAR|AVOID_NEAR|MUST_NOT_NEAR)$"
    )
    weight: int = Field(default=5, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=1000)


class PublicPreferenceUpdate(BaseModel):
    allow_other_tables: bool = True
    allow_other_zones: bool = True
    table_preferences: list[WeightedTablePreferenceInput] = Field(
        default_factory=list,
        max_length=500,
    )
    zone_preferences: list[WeightedZonePreferenceInput] = Field(
        default_factory=list,
        max_length=100,
    )
    adjacency_preferences: list[AdjacencyPreferenceInput] = Field(
        default_factory=list,
        max_length=100,
    )
    notes: str | None = Field(default=None, max_length=5000)
    submit: bool = False

    @model_validator(mode="after")
    def validate_unique_targets(self):
        table_ids = [item.table_id for item in self.table_preferences]
        if len(table_ids) != len(set(table_ids)):
            raise ValueError("Duplicate table preference")

        zone_ids = [item.zone_id for item in self.zone_preferences]
        if len(zone_ids) != len(set(zone_ids)):
            raise ValueError("Duplicate zone preference")

        target_ids = [
            item.target_booking_id
            for item in self.adjacency_preferences
        ]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("Duplicate adjacency target")

        if not self.allow_other_tables and not self.table_preferences:
            raise ValueError(
                "Select at least one table when other tables are not allowed"
            )

        if not self.allow_other_zones and not self.zone_preferences:
            raise ValueError(
                "Select at least one zone when other zones are not allowed"
            )

        return self


class GeneratePlansInput(BaseModel):
    variants: int = Field(default=3, ge=1, le=8)
    attempts_per_variant: int = Field(default=12, ge=3, le=50)
    near_distance: float = Field(default=220.0, ge=50, le=2000)


class PlanAssignmentInput(BaseModel):
    booking_id: UUID
    table_id: UUID
    start_slot: int = Field(default=1, ge=1, le=2)


class PlanUnassignInput(BaseModel):
    booking_id: UUID


class FinalizePlanInput(BaseModel):
    allow_incomplete: bool = False
