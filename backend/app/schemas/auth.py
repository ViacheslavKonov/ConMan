from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class BootstrapStatus(BaseModel):
    required: bool


class BootstrapRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=10, max_length=200)

    @field_validator("display_name", mode="before")
    @classmethod
    def strip_display_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class CurrentUserResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: str
