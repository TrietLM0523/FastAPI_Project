from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.repositories.user import UserRepository
from app.repositories.workspace import (
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberUpdateRole,
    WorkspaceUpdate,
)
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.services.permissions import WorkspacePermissions


class WorkspaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workspaces = WorkspaceRepository(session)
        self.members = WorkspaceMemberRepository(session)
        self.users = UserRepository(session)
        self.permissions = WorkspacePermissions(session)

    async def create(self, payload: WorkspaceCreate, actor: User) -> Workspace:
        try:
            workspace = await self.workspaces.create(
                name=payload.name, owner_id=actor.id
            )
            await self.members.add_member(workspace.id, actor.id, WorkspaceRole.OWNER)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(workspace)
        return workspace

    async def list(
        self, actor: User, page: int, limit: int
    ) -> tuple[list[Workspace], int]:
        if actor.role is UserRole.ADMIN:
            return await self.workspaces.list_all(page, limit)
        return await self.workspaces.list_for_user(actor.id, page, limit)

    async def get(self, workspace_id: int, actor: User) -> Workspace:
        workspace, _ = await self.permissions.require_member(workspace_id, actor)
        return workspace

    async def update(
        self, workspace_id: int, payload: WorkspaceUpdate, actor: User
    ) -> Workspace:
        workspace, _ = await self.permissions.require_owner(workspace_id, actor)
        await self.workspaces.update(workspace, payload.model_dump(exclude_unset=True))
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def delete(self, workspace_id: int, actor: User) -> None:
        workspace, _ = await self.permissions.require_owner(workspace_id, actor)
        await self.workspaces.delete(workspace)
        await self.session.commit()

    async def list_members(
        self, workspace_id: int, actor: User
    ) -> list[WorkspaceMember]:
        await self.permissions.require_member(workspace_id, actor)
        return await self.members.list_members(workspace_id)

    async def add_member(
        self, workspace_id: int, payload: WorkspaceMemberAdd, actor: User
    ) -> WorkspaceMember:
        await self.permissions.require_owner(workspace_id, actor)
        user = await self.users.get_by_email(str(payload.email))
        if user is None:
            raise NotFoundError("User not found")
        if await self.members.get_membership(workspace_id, user.id) is not None:
            raise ConflictError("User is already a workspace member")
        try:
            await self.members.add_member(workspace_id, user.id, payload.role)
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ConflictError("User is already a workspace member") from error
        membership = await self.members.get_membership(workspace_id, user.id)
        assert membership is not None
        return membership

    async def update_member_role(
        self,
        workspace_id: int,
        user_id: int,
        payload: WorkspaceMemberUpdateRole,
        actor: User,
    ) -> WorkspaceMember:
        await self.permissions.require_owner(workspace_id, actor)
        membership = await self.members.get_membership(workspace_id, user_id)
        if membership is None:
            raise NotFoundError("Workspace member not found")
        if membership.role is WorkspaceRole.OWNER:
            raise ForbiddenError("Workspace owner role cannot be changed")
        await self.members.update_role(membership, payload.role)
        await self.session.commit()
        return membership

    async def remove_member(self, workspace_id: int, user_id: int, actor: User) -> None:
        workspace, _ = await self.permissions.require_owner(workspace_id, actor)
        membership = await self.members.get_membership(workspace_id, user_id)
        if membership is None:
            raise NotFoundError("Workspace member not found")
        if user_id == workspace.owner_id or membership.role is WorkspaceRole.OWNER:
            raise ForbiddenError("Workspace owner cannot be removed")
        await self.members.remove_member(membership)
        await self.session.commit()
