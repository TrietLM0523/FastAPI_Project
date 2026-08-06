from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.task_list import TaskListCache
from app.models.label import Label
from app.models.project import Project, ProjectStatus
from app.models.user import User
from app.repositories.label import LabelRepository, TaskLabelRepository
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.schemas.label import LabelCreate, LabelUpdate
from app.services.exceptions import ConflictError, NotFoundError
from app.services.permissions import WorkspacePermissions


class LabelService:
    def __init__(
        self, session: AsyncSession, cache: TaskListCache | None = None
    ) -> None:
        self.session = session
        self.cache = cache
        self.labels = LabelRepository(session)
        self.links = TaskLabelRepository(session)
        self.projects = ProjectRepository(session)
        self.tasks = TaskRepository(session)
        self.permissions = WorkspacePermissions(session)

    async def create(self, project_id: int, payload: LabelCreate, actor: User) -> Label:
        project = await self._project(project_id)
        await self.permissions.require_editor(project.workspace_id, actor)
        self._ensure_active(project)
        normalized_name = self._normalize_name(payload.name)
        if await self.labels.get_by_project_and_name(project_id, normalized_name):
            raise ConflictError("Label name already exists in this project")
        try:
            label = await self.labels.create(
                project_id=project_id,
                name=payload.name,
                normalized_name=normalized_name,
                color=payload.color,
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ConflictError("Label name already exists in this project") from error
        await self.session.refresh(label)
        return label

    async def list(self, project_id: int, actor: User) -> list[Label]:
        project = await self._project(project_id)
        await self.permissions.require_member(project.workspace_id, actor)
        return await self.labels.list_by_project(project_id)

    async def get(self, label_id: int, actor: User) -> Label:
        label = await self._label(label_id)
        project = await self._project(label.project_id)
        await self.permissions.require_member(project.workspace_id, actor)
        return label

    async def update(self, label_id: int, payload: LabelUpdate, actor: User) -> Label:
        label = await self._label(label_id)
        project = await self._project(label.project_id)
        await self.permissions.require_editor(project.workspace_id, actor)
        self._ensure_active(project)
        data = payload.model_dump(exclude_unset=True)
        if "name" in data:
            normalized_name = self._normalize_name(str(data["name"]))
            duplicate = await self.labels.get_by_project_and_name(
                label.project_id, normalized_name
            )
            if duplicate is not None and duplicate.id != label.id:
                raise ConflictError("Label name already exists in this project")
            data["normalized_name"] = normalized_name
        try:
            await self.labels.update(label, data)
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ConflictError("Label name already exists in this project") from error
        await self.session.refresh(label)
        if self.cache is not None:
            await self.cache.invalidate(label.project_id)
        return label

    async def delete(self, label_id: int, actor: User) -> None:
        label = await self._label(label_id)
        project = await self._project(label.project_id)
        await self.permissions.require_editor(project.workspace_id, actor)
        self._ensure_active(project)
        project_id = label.project_id
        await self.labels.delete(label)
        await self.session.commit()
        if self.cache is not None:
            await self.cache.invalidate(project_id)

    async def attach(self, task_id: int, label_id: int, actor: User) -> None:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        label = await self._label(label_id)
        if task.project_id != label.project_id:
            raise ConflictError("Task and label must belong to the same project")
        await self.permissions.require_editor(task.project.workspace_id, actor)
        self._ensure_active(task.project)
        if await self.links.get_link(task_id, label_id) is not None:
            raise ConflictError("Label is already attached to this task")
        try:
            await self.links.attach(task_id, label_id)
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise ConflictError("Label is already attached to this task") from error
        if self.cache is not None:
            await self.cache.invalidate(task.project_id)

    async def detach(self, task_id: int, label_id: int, actor: User) -> None:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        label = await self._label(label_id)
        if task.project_id != label.project_id:
            raise ConflictError("Task and label must belong to the same project")
        await self.permissions.require_editor(task.project.workspace_id, actor)
        self._ensure_active(task.project)
        link = await self.links.get_link(task_id, label_id)
        if link is None:
            raise NotFoundError("Task label link not found")
        await self.links.detach(link)
        await self.session.commit()
        if self.cache is not None:
            await self.cache.invalidate(task.project_id)

    async def _project(self, project_id: int) -> Project:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        return project

    async def _label(self, label_id: int) -> Label:
        label = await self.labels.get_by_id(label_id)
        if label is None:
            raise NotFoundError("Label not found")
        return label

    @staticmethod
    def _normalize_name(name: str) -> str:
        return " ".join(name.casefold().split())

    @staticmethod
    def _ensure_active(project: Project) -> None:
        if project.status is ProjectStatus.ARCHIVED:
            raise ConflictError("Archived projects are read-only")
