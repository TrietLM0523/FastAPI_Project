from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.repositories.project import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.exceptions import ConflictError, NotFoundError
from app.services.permissions import WorkspacePermissions


class ProjectService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.projects = ProjectRepository(session)
        self.permissions = WorkspacePermissions(session)

    async def create(
        self, workspace_id: int, payload: ProjectCreate, actor: User
    ) -> Project:
        await self.permissions.require_editor(workspace_id, actor)
        project = await self.projects.create(
            workspace_id=workspace_id,
            name=payload.name,
            description=payload.description,
        )
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def list(self, workspace_id: int, actor: User) -> list[Project]:
        await self.permissions.require_member(workspace_id, actor)
        return await self.projects.list_by_workspace(workspace_id)

    async def get(self, project_id: int, actor: User) -> Project:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        await self.permissions.require_member(project.workspace_id, actor)
        return project

    async def update(
        self, project_id: int, payload: ProjectUpdate, actor: User
    ) -> Project:
        project = await self._get_for_mutation(project_id, actor)
        await self.projects.update(project, payload.model_dump(exclude_unset=True))
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def archive(self, project_id: int, actor: User) -> Project:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        await self.permissions.require_editor(project.workspace_id, actor)
        if project.status is ProjectStatus.ARCHIVED:
            raise ConflictError("Project is already archived")
        await self.projects.archive(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def _get_for_mutation(self, project_id: int, actor: User) -> Project:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        await self.permissions.require_editor(project.workspace_id, actor)
        if project.status is ProjectStatus.ARCHIVED:
            raise ConflictError("Archived projects are read-only")
        return project
