from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.services.exceptions import AuthenticationError, InactiveUserError


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.users.get_by_email(email)

        if user is None or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Incorrect email or password")

        if not user.is_active:
            raise InactiveUserError("User is inactive")

        return user

    async def issue_tokens(self, user: User) -> tuple[str, str]:
        raw_refresh_token = create_refresh_token()
        await self.refresh_tokens.add(
            user_id=user.id,
            token_hash=hash_token(raw_refresh_token),
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.refresh_token_expire_days),
        )
        await self.session.commit()
        return create_access_token(str(user.id)), raw_refresh_token

    async def refresh(self, raw_refresh_token: str) -> tuple[str, str]:
        stored_token = await self.refresh_tokens.get_by_hash(
            hash_token(raw_refresh_token)
        )
        if stored_token is None or stored_token.revoked_at is not None:
            raise AuthenticationError("Invalid refresh token")

        expires_at = stored_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise AuthenticationError("Invalid refresh token")

        user = await self.users.get_by_id(stored_token.user_id)
        if user is None:
            raise AuthenticationError("Invalid refresh token")
        if not user.is_active:
            raise InactiveUserError("User is inactive")

        stored_token.revoked_at = datetime.now(UTC)
        return await self.issue_tokens(user)

    async def logout(self, raw_refresh_token: str) -> None:
        stored_token = await self.refresh_tokens.get_by_hash(
            hash_token(raw_refresh_token)
        )
        if stored_token is None or stored_token.revoked_at is not None:
            raise AuthenticationError("Invalid refresh token")
        stored_token.revoked_at = datetime.now(UTC)
        await self.session.commit()
