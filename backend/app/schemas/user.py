from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: str
    active: bool


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=10, max_length=200)
    role: str = Field(pattern="^(ADMIN|MANAGER|REGISTRATION|VIEWER)$")
    active: bool = True


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=10, max_length=200)
    role: str | None = Field(
        default=None,
        pattern="^(ADMIN|MANAGER|REGISTRATION|VIEWER)$",
    )
    active: bool | None = None
