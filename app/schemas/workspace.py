from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.workspace import WorkspaceRole


class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value


class WorkspaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def trim_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("name cannot be null")
        return WorkspaceCreate.trim_name(value)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    role: WorkspaceRole

    def model_post_init(self, __context: object) -> None:
        if self.role is WorkspaceRole.OWNER:
            raise ValueError("OWNER cannot be assigned through membership endpoints")


class WorkspaceMemberUpdateRole(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: WorkspaceRole

    def model_post_init(self, __context: object) -> None:
        if self.role is WorkspaceRole.OWNER:
            raise ValueError("OWNER cannot be assigned through membership endpoints")


class WorkspaceMemberUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    workspace_id: int
    user_id: int
    role: WorkspaceRole
    created_at: datetime
    user: WorkspaceMemberUser


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1)
    pages: int = Field(ge=0)
