from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.user import AdminUserUpdate, UserCreate, UserUpdate
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)

    async def register(self, payload: UserCreate) -> User:
        email = str(payload.email)

        if await self.users.get_by_email(email) is not None:
            raise ConflictError("Email already exists")

        data = payload.model_dump(exclude={"password"}, mode="json")
        data.update(
            hashed_password=hash_password(payload.password),
            role=UserRole.USER,
            is_active=True,
        )

        try:
            return await self.users.create(data)
        except IntegrityError as error:
            raise ConflictError("Email already exists") from error

    async def get_user(self, user_id: int, with_tasks: bool = False) -> User:
        if with_tasks:
            user = await self.users.get_with_tasks(user_id)
        else:
            user = await self.users.get_by_id(user_id)

        if user is None:
            raise NotFoundError("User not found")

        return user

    async def list_users(
        self,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        return await self.users.list(page=page, page_size=page_size)

    async def update_user(
        self,
        user_id: int,
        payload: UserUpdate,
        actor: User,
    ) -> User:
        user = await self.get_user(user_id)

        if actor.role is not UserRole.ADMIN and actor.id != user.id:
            raise ForbiddenError("You cannot update this user")

        update_data = payload.model_dump(exclude_unset=True, mode="json")
        new_email = update_data.get("email")

        if new_email is not None:
            existing_user = await self.users.get_by_email(new_email)
            if existing_user is not None and existing_user.id != user.id:
                raise ConflictError("Email already exists")

        try:
            return await self.users.update(user, update_data)
        except IntegrityError as error:
            raise ConflictError("Email already exists") from error

    async def admin_update(
        self,
        user_id: int,
        payload: AdminUserUpdate,
    ) -> User:
        user = await self.get_user(user_id)
        update_data = payload.model_dump(exclude_unset=True)

        return await self.users.update(user, update_data)

    async def delete_user(self, user_id: int) -> None:
        user = await self.get_user(user_id)
        await self.users.delete(user)
