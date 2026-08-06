from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, name: str, owner_id: int) -> Workspace:
        workspace = Workspace(name=name, owner_id=owner_id)
        self.session.add(workspace)
        await self.session.flush()
        return workspace

    async def get_by_id(self, workspace_id: int) -> Workspace | None:
        return await self.session.get(Workspace, workspace_id)

    async def get_owned_by_name(self, owner_id: int, name: str) -> Workspace | None:
        return await self.session.scalar(
            select(Workspace).where(
                Workspace.owner_id == owner_id, Workspace.name == name
            )
        )

    async def list_for_user(
        self, user_id: int, page: int, limit: int
    ) -> tuple[list[Workspace], int]:
        criteria = WorkspaceMember.user_id == user_id
        statement = (
            select(Workspace)
            .join(WorkspaceMember)
            .where(criteria)
            .order_by(Workspace.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        count = await self.session.scalar(
            select(func.count())
            .select_from(Workspace)
            .join(WorkspaceMember)
            .where(criteria)
        )
        return list((await self.session.scalars(statement)).all()), int(count or 0)

    async def list_all(self, page: int, limit: int) -> tuple[list[Workspace], int]:
        statement = (
            select(Workspace)
            .order_by(Workspace.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        count = await self.session.scalar(select(func.count()).select_from(Workspace))
        return list((await self.session.scalars(statement)).all()), int(count or 0)

    async def update(self, workspace: Workspace, data: dict[str, object]) -> None:
        for field_name, value in data.items():
            setattr(workspace, field_name, value)
        await self.session.flush()

    async def delete(self, workspace: Workspace) -> None:
        await self.session.delete(workspace)


class WorkspaceMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_membership(
        self, workspace_id: int, user_id: int
    ) -> WorkspaceMember | None:
        statement = (
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return await self.session.scalar(statement)

    async def list_members(self, workspace_id: int) -> list[WorkspaceMember]:
        statement = (
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.created_at, WorkspaceMember.user_id)
        )
        return list((await self.session.scalars(statement)).all())

    async def add_member(
        self, workspace_id: int, user_id: int, role: WorkspaceRole
    ) -> WorkspaceMember:
        membership = WorkspaceMember(
            workspace_id=workspace_id, user_id=user_id, role=role
        )
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def update_role(
        self, membership: WorkspaceMember, role: WorkspaceRole
    ) -> None:
        membership.role = role
        await self.session.flush()

    async def remove_member(self, membership: WorkspaceMember) -> None:
        await self.session.delete(membership)

    async def is_member(self, workspace_id: int, user_id: int) -> bool:
        return (await self.get_membership(workspace_id, user_id)) is not None
