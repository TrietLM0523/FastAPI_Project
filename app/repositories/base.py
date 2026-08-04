from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(
        self,
        model: type[ModelT],
        session: AsyncSession,
    ) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, object_id: int) -> ModelT | None:
        return await self.session.get(self.model, object_id)

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ModelT], int]:
        offset = (page - 1) * page_size
        order_column = self.model.id

        statement = (
            select(self.model).order_by(order_column).offset(offset).limit(page_size)
        )

        count_statement = select(func.count()).select_from(self.model)

        result = await self.session.scalars(statement)
        total = await self.session.scalar(count_statement)

        return list(result.all()), int(total or 0)

    async def create(
        self,
        data: dict[str, Any],
    ) -> ModelT:
        instance = self.model(**data)
        self.session.add(instance)

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(instance)

        return instance

    async def update(
        self,
        instance: ModelT,
        data: dict[str, Any],
    ) -> ModelT:
        for field_name, value in data.items():
            setattr(instance, field_name, value)

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(instance)

        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)

        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
