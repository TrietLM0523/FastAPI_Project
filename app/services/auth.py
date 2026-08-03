from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.exceptions import AuthenticationError, InactiveUserError


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)

        if user is None or not verify_password(password, user.hashed_password):
            raise AuthenticationError

        if not user.is_active:
            raise InactiveUserError

        return user

    def create_token(self, user: User) -> str:
        return create_access_token(str(user.id))
