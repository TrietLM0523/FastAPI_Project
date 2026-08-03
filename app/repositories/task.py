from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Task, session)

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        owner_id: int | None = None,
    ) -> tuple[list[Task], int]:
        offset = (page - 1) * page_size

        statement = select(Task)
        count_statement = select(func.count()).select_from(Task)

        if owner_id is not None:
            statement = statement.where(Task.owner_id == owner_id)
            count_statement = count_statement.where(
                Task.owner_id == owner_id,
            )

        statement = statement.order_by(Task.id).offset(offset).limit(page_size)

        result = await self.session.scalars(statement)
        total = await self.session.scalar(count_statement)

        return list(result.all()), int(total or 0)

    async def get_by_id_and_owner(
        self,
        task_id: int,
        owner_id: int,
    ) -> Task | None:
        statement = select(Task).where(
            Task.id == task_id,
            Task.owner_id == owner_id,
        )

        return await self.session.scalar(statement)
