from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.task import Task, TaskPriority, TaskStatus


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: dict[str, object]) -> Task:
        task = Task(**data)
        self.session.add(task)
        await self.session.flush()
        return task

    async def get_by_id(self, task_id: int) -> Task | None:
        statement = (
            select(Task)
            .options(selectinload(Task.project), selectinload(Task.labels))
            .where(Task.id == task_id)
        )
        return await self.session.scalar(statement)

    async def list_by_project_filtered(
        self,
        project_id: int,
        *,
        status: TaskStatus | None,
        priority: TaskPriority | None,
        assignee_id: int | None,
        page: int,
        limit: int,
    ) -> tuple[list[Task], int]:
        filters = [Task.project_id == project_id]
        if status is not None:
            filters.append(Task.status == status)
        if priority is not None:
            filters.append(Task.priority == priority)
        if assignee_id is not None:
            filters.append(Task.assignee_id == assignee_id)

        statement = (
            select(Task)
            .options(selectinload(Task.labels))
            .where(*filters)
            .order_by(Task.id)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        count_statement = select(func.count()).select_from(Task).where(*filters)
        tasks = list((await self.session.scalars(statement)).all())
        total = int(await self.session.scalar(count_statement) or 0)
        return tasks, total

    async def list_legacy(
        self,
        *,
        created_by: int | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Task], int]:
        filters = [] if created_by is None else [Task.created_by == created_by]
        statement = (
            select(Task)
            .options(selectinload(Task.labels))
            .where(*filters)
            .order_by(Task.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = select(func.count()).select_from(Task).where(*filters)
        tasks = list((await self.session.scalars(statement)).all())
        total = int(await self.session.scalar(count_statement) or 0)
        return tasks, total

    async def update(self, task: Task, data: dict[str, object]) -> None:
        for field_name, value in data.items():
            setattr(task, field_name, value)
        await self.session.flush()

    async def delete(self, task: Task) -> None:
        await self.session.delete(task)
