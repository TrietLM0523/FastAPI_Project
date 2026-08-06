from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectStatus


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, workspace_id: int, name: str, description: str | None
    ) -> Project:
        project = Project(workspace_id=workspace_id, name=name, description=description)
        self.session.add(project)
        await self.session.flush()
        return project

    async def get_by_id(self, project_id: int) -> Project | None:
        return await self.session.get(Project, project_id)

    async def get_by_workspace_and_name(
        self, workspace_id: int, name: str
    ) -> Project | None:
        return await self.session.scalar(
            select(Project).where(
                Project.workspace_id == workspace_id, Project.name == name
            )
        )

    async def list_by_workspace(self, workspace_id: int) -> list[Project]:
        statement = (
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def update(self, project: Project, data: dict[str, object]) -> None:
        for field_name, value in data.items():
            setattr(project, field_name, value)
        await self.session.flush()

    async def archive(self, project: Project) -> None:
        project.status = ProjectStatus.ARCHIVED
        await self.session.flush()
