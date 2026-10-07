from pydantic import BaseModel, Field


class CheckInActionInput(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class BadgeIssueInput(BaseModel):
    badge_number: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
