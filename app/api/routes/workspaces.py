from math import ceil
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, DBSession
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceMemberAdd,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdateRole,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace import WorkspaceService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate, session: DBSession, current_user: CurrentUser
) -> WorkspaceResponse:
    workspace = await WorkspaceService(session).create(payload, current_user)
    return WorkspaceResponse.model_validate(workspace)


@router.get("", response_model=WorkspaceListResponse)
async def list_workspaces(
    session: DBSession,
    current_user: CurrentUser,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> WorkspaceListResponse:
    workspaces, total = await WorkspaceService(session).list(current_user, page, limit)
    return WorkspaceListResponse(
        items=[WorkspaceResponse.model_validate(item) for item in workspaces],
        total=total,
        page=page,
        limit=limit,
        pages=ceil(total / limit) if total else 0,
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: int, session: DBSession, current_user: CurrentUser
) -> WorkspaceResponse:
    workspace = await WorkspaceService(session).get(workspace_id, current_user)
    return WorkspaceResponse.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: int,
    payload: WorkspaceUpdate,
    session: DBSession,
    current_user: CurrentUser,
) -> WorkspaceResponse:
    workspace = await WorkspaceService(session).update(
        workspace_id, payload, current_user
    )
    return WorkspaceResponse.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: int, session: DBSession, current_user: CurrentUser
) -> Response:
    await WorkspaceService(session).delete(workspace_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: int, session: DBSession, current_user: CurrentUser
) -> list[WorkspaceMemberResponse]:
    members = await WorkspaceService(session).list_members(workspace_id, current_user)
    return [WorkspaceMemberResponse.model_validate(item) for item in members]


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_workspace_member(
    workspace_id: int,
    payload: WorkspaceMemberAdd,
    session: DBSession,
    current_user: CurrentUser,
) -> WorkspaceMemberResponse:
    member = await WorkspaceService(session).add_member(
        workspace_id, payload, current_user
    )
    return WorkspaceMemberResponse.model_validate(member)


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
)
async def update_workspace_member_role(
    workspace_id: int,
    user_id: int,
    payload: WorkspaceMemberUpdateRole,
    session: DBSession,
    current_user: CurrentUser,
) -> WorkspaceMemberResponse:
    member = await WorkspaceService(session).update_member_role(
        workspace_id, user_id, payload, current_user
    )
    return WorkspaceMemberResponse.model_validate(member)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_workspace_member(
    workspace_id: int,
    user_id: int,
    session: DBSession,
    current_user: CurrentUser,
) -> Response:
    await WorkspaceService(session).remove_member(workspace_id, user_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
