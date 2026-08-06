from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment
from app.models.task import Task


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, task_id: int, author_id: int, content: str) -> Comment:
        comment = Comment(task_id=task_id, author_id=author_id, content=content)
        self.session.add(comment)
        await self.session.flush()
        return comment

    async def get_by_id(self, comment_id: int) -> Comment | None:
        statement = (
            select(Comment)
            .options(selectinload(Comment.task).selectinload(Task.project))
            .where(Comment.id == comment_id)
        )
        return await self.session.scalar(statement)

    async def list_by_task(self, task_id: int) -> list[Comment]:
        statement = (
            select(Comment)
            .options(selectinload(Comment.author))
            .where(Comment.task_id == task_id)
            .order_by(Comment.created_at, Comment.id)
        )
        return list((await self.session.scalars(statement)).all())

    async def delete(self, comment: Comment) -> None:
        await self.session.delete(comment)
