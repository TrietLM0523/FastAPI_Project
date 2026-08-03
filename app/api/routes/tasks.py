from math import ceil
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.dependencies import CurrentUser, DBSession
from app.schemas.pagination import PaginatedResponse
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from app.services.exceptions import ForbiddenError, NotFoundError
from app.services.task import TaskService

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)


def raise_task_error(error: NotFoundError | ForbiddenError) -> None:
    if isinstance(error, NotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        ) from error

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission for this task",
    ) from error


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    session: DBSession,
    current_user: CurrentUser,
) -> TaskResponse:
    task = await TaskService(session).create(payload, current_user)
    return TaskResponse.model_validate(task)


@router.get("", response_model=PaginatedResponse[TaskResponse])
async def list_tasks(
    session: DBSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    owner_id: Annotated[int | None, Query(gt=0)] = None,
) -> PaginatedResponse[TaskResponse]:
    tasks, total = await TaskService(session).list_for_user(
        current_user=current_user,
        page=page,
        page_size=page_size,
        owner_id=owner_id,
    )

    return PaginatedResponse[TaskResponse](
        items=[TaskResponse.model_validate(task) for task in tasks],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    session: DBSession,
    current_user: CurrentUser,
) -> TaskResponse:
    try:
        task = await TaskService(session).get(task_id, current_user)
    except (NotFoundError, ForbiddenError) as error:
        raise_task_error(error)

    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: DBSession,
    current_user: CurrentUser,
) -> TaskResponse:
    try:
        task = await TaskService(session).update(task_id, payload, current_user)
    except (NotFoundError, ForbiddenError) as error:
        raise_task_error(error)

    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    session: DBSession,
    current_user: CurrentUser,
) -> Response:
    try:
        await TaskService(session).delete(task_id, current_user)
    except (NotFoundError, ForbiddenError) as error:
        raise_task_error(error)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
