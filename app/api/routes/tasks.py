from math import ceil
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, DBSession
from app.models.task import TaskPriority, TaskStatus
from app.schemas.pagination import PaginatedResponse
from app.schemas.task import (
    LegacyTaskCreate,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskStatusUpdate,
    TaskUpdate,
)
from app.services.task import TaskService

router = APIRouter(tags=["Tasks"])


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
)
async def create_legacy_task(
    payload: LegacyTaskCreate,
    session: DBSession,
    current_user: CurrentUser,
) -> TaskResponse:
    task = await TaskService(session).create_legacy(payload, current_user)
    return TaskResponse.model_validate(task)


@router.get("/tasks", response_model=PaginatedResponse[TaskResponse], deprecated=True)
async def list_legacy_tasks(
    session: DBSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    owner_id: Annotated[int | None, Query(gt=0)] = None,
) -> PaginatedResponse[TaskResponse]:
    tasks, total = await TaskService(session).list_legacy(
        current_user, page=page, page_size=page_size, owner_id=owner_id
    )
    return PaginatedResponse[TaskResponse](
        items=[TaskResponse.model_validate(item) for item in tasks],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
    )


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: int,
    payload: TaskCreate,
    session: DBSession,
    current_user: CurrentUser,
) -> TaskResponse:
    task = await TaskService(session).create(project_id, payload, current_user)
    return TaskResponse.model_validate(task)


@router.get("/projects/{project_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    project_id: int,
    session: DBSession,
    current_user: CurrentUser,
    status_filter: Annotated[TaskStatus | None, Query(alias="status")] = None,
    priority: Annotated[TaskPriority | None, Query()] = None,
    assignee_id: Annotated[int | None, Query(gt=0)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TaskListResponse:
    tasks, total = await TaskService(session).list_by_project(
        project_id,
        current_user,
        status=status_filter,
        priority=priority,
        assignee_id=assignee_id,
        page=page,
        limit=limit,
    )
    return TaskListResponse(
        items=[TaskResponse.model_validate(item) for item in tasks],
        total=total,
        page=page,
        limit=limit,
        pages=ceil(total / limit) if total else 0,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int, session: DBSession, current_user: CurrentUser
) -> TaskResponse:
    task = await TaskService(session).get(task_id, current_user)
    return TaskResponse.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    session: DBSession,
    current_user: CurrentUser,
) -> TaskResponse:
    task = await TaskService(session).update(task_id, payload, current_user)
    return TaskResponse.model_validate(task)


@router.patch("/tasks/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: int,
    payload: TaskStatusUpdate,
    session: DBSession,
    current_user: CurrentUser,
) -> TaskResponse:
    task = await TaskService(session).update_status(task_id, payload, current_user)
    return TaskResponse.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int, session: DBSession, current_user: CurrentUser
) -> Response:
    await TaskService(session).delete(task_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
