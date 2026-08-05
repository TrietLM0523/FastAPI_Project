from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole
from app.models.workspace import WorkspaceMember, WorkspaceRole
from app.repositories.project import ProjectRepository
from app.repositories.task import TaskRepository
from app.repositories.workspace import (
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from app.schemas.task import (
    LegacyTaskCreate,
    TaskCreate,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.services.permissions import WorkspacePermissions


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.tasks = TaskRepository(session)
        self.projects = ProjectRepository(session)
        self.members = WorkspaceMemberRepository(session)
        self.workspaces = WorkspaceRepository(session)
        self.permissions = WorkspacePermissions(session)

    async def create(self, project_id: int, payload: TaskCreate, actor: User) -> Task:
        project = await self._get_project(project_id)
        await self.permissions.require_editor(project.workspace_id, actor)
        self._ensure_active(project)
        await self._validate_assignee(project.workspace_id, payload.assignee_id)
        data = payload.model_dump()
        data.update(project_id=project.id, created_by=actor.id)
        task = await self.tasks.create(data)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def list_by_project(
        self,
        project_id: int,
        actor: User,
        *,
        status: TaskStatus | None,
        priority: TaskPriority | None,
        assignee_id: int | None,
        page: int,
        limit: int,
    ) -> tuple[list[Task], int]:
        project = await self._get_project(project_id)
        await self.permissions.require_member(project.workspace_id, actor)
        return await self.tasks.list_by_project_filtered(
            project_id,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            page=page,
            limit=limit,
        )

    async def get(self, task_id: int, actor: User) -> Task:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        await self.permissions.require_member(task.project.workspace_id, actor)
        return task

    async def update(self, task_id: int, payload: TaskUpdate, actor: User) -> Task:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        self._ensure_active(task.project)
        _, membership = await self.permissions.require_member(
            task.project.workspace_id, actor
        )
        fields = payload.model_fields_set
        has_edit_permission = self._can_edit(actor, membership)
        is_assignee_status_only = task.assignee_id == actor.id and fields == {"status"}
        if not has_edit_permission and not is_assignee_status_only:
            raise ForbiddenError("Task update permission denied")
        if has_edit_permission:
            await self._validate_assignee(
                task.project.workspace_id, payload.assignee_id, fields
            )
        update_data = payload.model_dump(exclude_unset=True)
        completed = update_data.pop("completed", None)
        if "completed" in fields:
            update_data["status"] = TaskStatus.DONE if completed else TaskStatus.TODO
        await self.tasks.update(task, update_data)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def create_legacy(self, payload: LegacyTaskCreate, actor: User) -> Task:
        workspace = await self.workspaces.get_owned_by_name(
            actor.id, "Personal Workspace"
        )
        if workspace is None:
            workspace = await self.workspaces.create(
                name="Personal Workspace", owner_id=actor.id
            )
            await self.members.add_member(workspace.id, actor.id, WorkspaceRole.OWNER)
        project = await self.projects.get_by_workspace_and_name(
            workspace.id, "Personal Tasks"
        )
        if project is None:
            project = await self.projects.create(
                workspace_id=workspace.id,
                name="Personal Tasks",
                description="Day 5 task compatibility project",
            )
        task = await self.tasks.create(
            {
                **payload.model_dump(),
                "project_id": project.id,
                "created_by": actor.id,
            }
        )
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def list_legacy(
        self,
        actor: User,
        *,
        page: int,
        page_size: int,
        owner_id: int | None,
    ) -> tuple[list[Task], int]:
        visible_creator = owner_id if actor.role is UserRole.ADMIN else actor.id
        return await self.tasks.list_legacy(
            created_by=visible_creator, page=page, page_size=page_size
        )

    async def update_status(
        self, task_id: int, payload: TaskStatusUpdate, actor: User
    ) -> Task:
        return await self.update(task_id, TaskUpdate(status=payload.status), actor)

    async def delete(self, task_id: int, actor: User) -> None:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        self._ensure_active(task.project)
        _, membership = await self.permissions.require_member(
            task.project.workspace_id, actor
        )
        can_delete = actor.role is UserRole.ADMIN or (
            membership is not None
            and (
                membership.role is WorkspaceRole.OWNER
                or (
                    membership.role is WorkspaceRole.EDITOR
                    and task.created_by == actor.id
                )
            )
        )
        if not can_delete:
            raise ForbiddenError("Task delete permission denied")
        await self.tasks.delete(task)
        await self.session.commit()

    async def _get_project(self, project_id: int) -> Project:
        project = await self.projects.get_by_id(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        return project

    async def _validate_assignee(
        self,
        workspace_id: int,
        assignee_id: int | None,
        supplied_fields: set[str] | None = None,
    ) -> None:
        if supplied_fields is not None and "assignee_id" not in supplied_fields:
            return
        if assignee_id is not None and not await self.members.is_member(
            workspace_id, assignee_id
        ):
            raise ForbiddenError("Assignee must be a workspace member")

    @staticmethod
    def _can_edit(actor: User, membership: WorkspaceMember | None) -> bool:
        return actor.role is UserRole.ADMIN or (
            membership is not None
            and membership.role in {WorkspaceRole.OWNER, WorkspaceRole.EDITOR}
        )

    @staticmethod
    def _ensure_active(project: Project) -> None:
        if project.status is ProjectStatus.ARCHIVED:
            raise ConflictError("Archived projects are read-only")
