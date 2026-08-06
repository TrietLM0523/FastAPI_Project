from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DBSession, TaskCache
from app.schemas.label import LabelCreate, LabelResponse, LabelUpdate
from app.services.label import LabelService

router = APIRouter(tags=["Labels"])


@router.post(
    "/projects/{project_id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project label",
)
async def create_label(
    project_id: int,
    payload: LabelCreate,
    session: DBSession,
    current_user: CurrentUser,
    cache: TaskCache,
) -> LabelResponse:
    label = await LabelService(session, cache).create(project_id, payload, current_user)
    return LabelResponse.model_validate(label)


@router.get(
    "/projects/{project_id}/labels",
    response_model=list[LabelResponse],
    summary="List project labels",
)
async def list_labels(
    project_id: int, session: DBSession, current_user: CurrentUser
) -> list[LabelResponse]:
    labels = await LabelService(session).list(project_id, current_user)
    return [LabelResponse.model_validate(label) for label in labels]


@router.get("/labels/{label_id}", response_model=LabelResponse, summary="Get a label")
async def get_label(
    label_id: int, session: DBSession, current_user: CurrentUser
) -> LabelResponse:
    label = await LabelService(session).get(label_id, current_user)
    return LabelResponse.model_validate(label)


@router.patch(
    "/labels/{label_id}", response_model=LabelResponse, summary="Update a label"
)
async def update_label(
    label_id: int,
    payload: LabelUpdate,
    session: DBSession,
    current_user: CurrentUser,
    cache: TaskCache,
) -> LabelResponse:
    label = await LabelService(session, cache).update(label_id, payload, current_user)
    return LabelResponse.model_validate(label)


@router.delete(
    "/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a label",
)
async def delete_label(
    label_id: int,
    session: DBSession,
    current_user: CurrentUser,
    cache: TaskCache,
) -> Response:
    await LabelService(session, cache).delete(label_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/tasks/{task_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Attach a label to a task",
)
async def attach_label(
    task_id: int,
    label_id: int,
    session: DBSession,
    current_user: CurrentUser,
    cache: TaskCache,
) -> Response:
    await LabelService(session, cache).attach(task_id, label_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/tasks/{task_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Detach a label from a task",
)
async def detach_label(
    task_id: int,
    label_id: int,
    session: DBSession,
    current_user: CurrentUser,
    cache: TaskCache,
) -> Response:
    await LabelService(session, cache).detach(task_id, label_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
