from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.repositories.workspace import (
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from app.services.exceptions import ForbiddenError, NotFoundError


class WorkspacePermissions:
    def __init__(self, session: AsyncSession) -> None:
        self.workspaces = WorkspaceRepository(session)
        self.members = WorkspaceMemberRepository(session)

    async def get_workspace(self, workspace_id: int) -> Workspace:
        workspace = await self.workspaces.get_by_id(workspace_id)
        if workspace is None:
            raise NotFoundError("Workspace not found")
        return workspace

    async def require_member(
        self, workspace_id: int, actor: User
    ) -> tuple[Workspace, WorkspaceMember | None]:
        workspace = await self.get_workspace(workspace_id)
        if actor.role is UserRole.ADMIN:
            return workspace, None
        membership = await self.members.get_membership(workspace_id, actor.id)
        if membership is None:
            raise ForbiddenError("Workspace access denied")
        return workspace, membership

    async def require_owner(
        self, workspace_id: int, actor: User
    ) -> tuple[Workspace, WorkspaceMember | None]:
        workspace, membership = await self.require_member(workspace_id, actor)
        if actor.role is not UserRole.ADMIN and (
            membership is None or membership.role is not WorkspaceRole.OWNER
        ):
            raise ForbiddenError("Workspace owner permission required")
        return workspace, membership

    async def require_editor(
        self, workspace_id: int, actor: User
    ) -> tuple[Workspace, WorkspaceMember | None]:
        workspace, membership = await self.require_member(workspace_id, actor)
        if actor.role is not UserRole.ADMIN and (
            membership is None
            or membership.role not in {WorkspaceRole.OWNER, WorkspaceRole.EDITOR}
        ):
            raise ForbiddenError("Workspace edit permission required")
        return workspace, membership
