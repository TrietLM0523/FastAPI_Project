from math import ceil
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import DBSession
from app.core.security import hash_password
from app.repositories.user import UserRepository
from app.schemas.pagination import PaginatedResponse
from app.schemas.user import (
    UserCreate,
    UserResponse,
    UserUpdate,
    UserWithTasks,
)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    payload: UserCreate,
    session: DBSession,
) -> UserResponse:
    repository = UserRepository(session)

    existing_user = await repository.get_by_email(
        str(payload.email),
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    user_data = payload.model_dump(
        exclude={"password"},
        mode="json",
    )

    user_data["hashed_password"] = hash_password(
        payload.password,
    )

    user = await repository.create(user_data)

    return UserResponse.model_validate(user)


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
)
async def list_users(
    session: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[UserResponse]:
    repository = UserRepository(session)

    users, total = await repository.list(
        page=page,
        page_size=page_size,
    )

    return PaginatedResponse[UserResponse](
        items=[UserResponse.model_validate(user) for user in users],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get(
    "/{user_id}",
    response_model=UserWithTasks,
)
async def get_user(
    user_id: int,
    session: DBSession,
) -> UserWithTasks:
    repository = UserRepository(session)

    user = await repository.get_with_tasks(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserWithTasks.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    session: DBSession,
) -> UserResponse:
    repository = UserRepository(session)

    user = await repository.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True,
        mode="json",
    )

    new_email = update_data.get("email")

    if new_email is not None:
        existing_user = await repository.get_by_email(new_email)

        if existing_user is not None and existing_user.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )

    updated_user = await repository.update(
        user,
        update_data,
    )

    return UserResponse.model_validate(updated_user)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: int,
    session: DBSession,
) -> Response:
    repository = UserRepository(session)

    user = await repository.get_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await repository.delete(user)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
