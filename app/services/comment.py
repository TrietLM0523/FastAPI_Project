from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.models.project import ProjectStatus
from app.models.user import User, UserRole
from app.models.workspace import WorkspaceRole
from app.repositories.comment import CommentRepository
from app.repositories.task import TaskRepository
from app.schemas.comment import CommentCreate
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.services.permissions import WorkspacePermissions


class CommentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.comments = CommentRepository(session)
        self.tasks = TaskRepository(session)
        self.permissions = WorkspacePermissions(session)

    async def create(
        self, task_id: int, payload: CommentCreate, actor: User
    ) -> Comment:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        await self.permissions.require_editor(task.project.workspace_id, actor)
        self._ensure_active(task.project.status)
        comment = await self.comments.create(
            task_id=task_id, author_id=actor.id, content=payload.content
        )
        await self.session.commit()
        await self.session.refresh(comment)
        return comment

    async def list(self, task_id: int, actor: User) -> list[Comment]:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        await self.permissions.require_member(task.project.workspace_id, actor)
        return await self.comments.list_by_task(task_id)

    async def delete(self, comment_id: int, actor: User) -> None:
        comment = await self.comments.get_by_id(comment_id)
        if comment is None:
            raise NotFoundError("Comment not found")
        task = comment.task
        self._ensure_active(task.project.status)
        _, membership = await self.permissions.require_member(
            task.project.workspace_id, actor
        )
        can_delete = actor.role is UserRole.ADMIN or (
            membership is not None
            and (
                membership.role is WorkspaceRole.OWNER
                or (
                    membership.role is WorkspaceRole.EDITOR
                    and comment.author_id == actor.id
                )
            )
        )
        if not can_delete:
            raise ForbiddenError("Comment delete permission denied")
        await self.comments.delete(comment)
        await self.session.commit()

    @staticmethod
    def _ensure_active(status: ProjectStatus) -> None:
        if status is ProjectStatus.ARCHIVED:
            raise ConflictError("Archived projects are read-only")
