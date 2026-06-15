# src/modules/users/schemas.py

from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    birthdate: date
    cpf: str = Field(..., min_length=11, max_length=14)
    phone_number: str = Field(..., min_length=10, max_length=20)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=120)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    birthdate: date | None = None
    cpf: str | None = Field(default=None, min_length=11, max_length=14)
    phone_number: str | None = Field(default=None, min_length=10, max_length=20)


class UserCreateResponse(BaseModel):
    uuid: UUID
    full_name: str
    email: EmailStr
    birthdate: date
    cpf: str
    phone_number: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
