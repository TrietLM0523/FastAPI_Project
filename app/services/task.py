from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.user import User, UserRole
from app.repositories.task import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.exceptions import ForbiddenError, NotFoundError


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.tasks = TaskRepository(session)

    async def create(self, payload: TaskCreate, owner: User) -> Task:
        data = payload.model_dump()
        data["owner_id"] = owner.id

        return await self.tasks.create(data)

    async def list_for_user(
        self,
        current_user: User,
        page: int,
        page_size: int,
        owner_id: int | None = None,
    ) -> tuple[list[Task], int]:
        visible_owner_id = (
            owner_id if current_user.role is UserRole.ADMIN else current_user.id
        )

        return await self.tasks.list_tasks(
            page=page,
            page_size=page_size,
            owner_id=visible_owner_id,
        )

    async def get(self, task_id: int, current_user: User) -> Task:
        task = await self.tasks.get_by_id(task_id)

        if task is None:
            raise NotFoundError("Task not found")

        self._ensure_access(task, current_user)
        return task

    async def update(
        self,
        task_id: int,
        payload: TaskUpdate,
        current_user: User,
    ) -> Task:
        task = await self.get(task_id, current_user)
        update_data = payload.model_dump(exclude_unset=True)

        return await self.tasks.update(task, update_data)

    async def delete(self, task_id: int, current_user: User) -> None:
        task = await self.get(task_id, current_user)
        await self.tasks.delete(task)

    @staticmethod
    def _ensure_access(task: Task, current_user: User) -> None:
        if current_user.role is not UserRole.ADMIN and task.owner_id != current_user.id:
            raise ForbiddenError("You do not have permission for this task")
