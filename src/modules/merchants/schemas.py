from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class MerchantNameCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class MerchantNameUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class MerchantNameResponse(BaseModel):
    uuid: UUID
    name: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
