from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.background.notifications import LoggingEmailSender, NotificationSender
from app.cache.task_list import TaskListCache
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.repositories.user import UserRepository

DBSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_prefix}/auth/login",
)


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    session: DBSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    try:
        subject = decode_access_token(token)
        user_id = int(subject)
    except (jwt.InvalidTokenError, ValueError) as error:
        raise credentials_exception() from error

    user = await UserRepository(session).get_by_id(user_id)

    if user is None:
        raise credentials_exception()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    if current_user.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permission required",
        )

    return current_user


AdminUser = Annotated[User, Depends(require_admin)]


def get_task_list_cache(request: Request) -> TaskListCache:
    return request.app.state.task_list_cache


TaskCache = Annotated[TaskListCache, Depends(get_task_list_cache)]

notification_sender: NotificationSender = LoggingEmailSender()


def get_notification_sender() -> NotificationSender:
    return notification_sender


NotificationSenderDep = Annotated[NotificationSender, Depends(get_notification_sender)]
