from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DBSession
from app.schemas.comment import CommentCreate, CommentResponse
from app.services.comment import CommentService

router = APIRouter(tags=["Comments"])


@router.post(
    "/tasks/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a task",
)
async def create_comment(
    task_id: int,
    payload: CommentCreate,
    session: DBSession,
    current_user: CurrentUser,
) -> CommentResponse:
    comment = await CommentService(session).create(task_id, payload, current_user)
    return CommentResponse.model_validate(comment)


@router.get(
    "/tasks/{task_id}/comments",
    response_model=list[CommentResponse],
    summary="List task comments",
)
async def list_comments(
    task_id: int, session: DBSession, current_user: CurrentUser
) -> list[CommentResponse]:
    comments = await CommentService(session).list(task_id, current_user)
    return [CommentResponse.model_validate(comment) for comment in comments]


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment",
)
async def delete_comment(
    comment_id: int, session: DBSession, current_user: CurrentUser
) -> Response:
    await CommentService(session).delete(comment_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
