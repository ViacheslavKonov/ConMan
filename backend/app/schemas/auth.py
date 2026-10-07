from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class CurrentUserResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: str
