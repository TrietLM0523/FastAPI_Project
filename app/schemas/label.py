import re
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class LabelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    color: str

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        value = value.strip().upper()
        if not HEX_COLOR.fullmatch(value):
            raise ValueError("color must use #RRGGBB format")
        return value


class LabelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = None

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return LabelCreate.trim_name(value)

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("color cannot be null")
        return LabelCreate.validate_color(value)

    @model_validator(mode="after")
    def require_a_field(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class LabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    color: str
    created_at: datetime
    updated_at: datetime
