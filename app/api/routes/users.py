from math import ceil
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import AdminUser, CurrentUser, DBSession
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import (
    AdminUserUpdate,
    ChangePasswordRequest,
    UserCreate,
    UserResponse,
    UserUpdate,
    UserWithTasks,
)
from app.services.user import UserService

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(payload: UserCreate, session: DBSession) -> UserResponse:
    user = await UserService(session).register(payload)
    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    payload: UserUpdate,
    session: DBSession,
    current_user: CurrentUser,
) -> UserResponse:
    user = await UserService(session).update_user(
        current_user.id, payload, current_user
    )
    return UserResponse.model_validate(user)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_current_user_password(
    payload: ChangePasswordRequest,
    session: DBSession,
    current_user: CurrentUser,
) -> Response:
    await UserService(session).change_password(current_user, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    session: DBSession,
    admin_user: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[UserResponse]:
    users, total = await UserService(session).list_users(page, page_size)

    return PaginatedResponse[UserResponse](
        items=[UserResponse.model_validate(user) for user in users],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/{user_id}", response_model=UserWithTasks)
async def get_user(
    user_id: int,
    session: DBSession,
    admin_user: AdminUser,
) -> UserWithTasks:
    user = await UserService(session).get_user(user_id, with_tasks=True)
    return UserWithTasks.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    session: DBSession,
    current_user: CurrentUser,
) -> UserResponse:
    user = await UserService(session).update_user(
        user_id,
        payload,
        current_user,
    )
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/admin", response_model=UserResponse)
async def admin_update_user(
    user_id: int,
    payload: AdminUserUpdate,
    session: DBSession,
    admin_user: AdminUser,
) -> UserResponse:
    user = await UserService(session).admin_update(user_id, payload)
    return UserResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: DBSession,
    admin_user: AdminUser,
) -> Response:
    await UserService(session).delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
