from math import ceil
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import DBSession
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.schemas.pagination import PaginatedResponse
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    payload: TaskCreate,
    session: DBSession,
) -> TaskResponse:
    user_repository = UserRepository(session)
    task_repository = TaskRepository(session)

    user = await user_repository.get_by_id(payload.user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    task = await task_repository.create(
        payload.model_dump(),
    )

    return TaskResponse.model_validate(task)


@router.get(
    "",
    response_model=PaginatedResponse[TaskResponse],
)
async def list_tasks(
    session: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    user_id: Annotated[int | None, Query(gt=0)] = None,
) -> PaginatedResponse[TaskResponse]:
    repository = TaskRepository(session)

    tasks, total = await repository.list_tasks(
        page=page,
        page_size=page_size,
        user_id=user_id,
    )

    return PaginatedResponse[TaskResponse](
        items=[TaskResponse.model_validate(task) for task in tasks],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
)
async def get_task(
    task_id: int,
    session: DBSession,
) -> TaskResponse:
    repository = TaskRepository(session)

    task = await repository.get_by_id(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return TaskResponse.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: DBSession,
) -> TaskResponse:
    task_repository = TaskRepository(session)
    user_repository = UserRepository(session)

    task = await task_repository.get_by_id(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    new_user_id = update_data.get("user_id")

    if new_user_id is not None:
        user = await user_repository.get_by_id(new_user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

    updated_task = await task_repository.update(
        task,
        update_data,
    )

    return TaskResponse.model_validate(updated_task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_task(
    task_id: int,
    session: DBSession,
) -> Response:
    repository = TaskRepository(session)

    task = await repository.get_by_id(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    await repository.delete(task)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
