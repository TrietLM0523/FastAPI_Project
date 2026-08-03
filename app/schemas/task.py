from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    completed: bool | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> Self:
        for field_name in ("title", "completed"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"{field_name} cannot be null")

        return self


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    completed: bool
    owner_id: int
    created_at: datetime
    updated_at: datetime
