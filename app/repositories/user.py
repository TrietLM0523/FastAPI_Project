from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)

        return await self.session.scalar(statement)

    async def get_with_tasks(self, user_id: int) -> User | None:
        statement = (
            select(User).options(selectinload(User.tasks)).where(User.id == user_id)
        )

        return await self.session.scalar(statement)
