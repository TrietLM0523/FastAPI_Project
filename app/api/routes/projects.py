from fastapi import APIRouter, status

from app.api.dependencies import CurrentUser, DBSession
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project import ProjectService

router = APIRouter(tags=["Projects"])


@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    workspace_id: int,
    payload: ProjectCreate,
    session: DBSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    project = await ProjectService(session).create(workspace_id, payload, current_user)
    return ProjectResponse.model_validate(project)


@router.get("/workspaces/{workspace_id}/projects", response_model=list[ProjectResponse])
async def list_projects(
    workspace_id: int, session: DBSession, current_user: CurrentUser
) -> list[ProjectResponse]:
    projects = await ProjectService(session).list(workspace_id, current_user)
    return [ProjectResponse.model_validate(item) for item in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int, session: DBSession, current_user: CurrentUser
) -> ProjectResponse:
    project = await ProjectService(session).get(project_id, current_user)
    return ProjectResponse.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    session: DBSession,
    current_user: CurrentUser,
) -> ProjectResponse:
    project = await ProjectService(session).update(project_id, payload, current_user)
    return ProjectResponse.model_validate(project)


@router.post("/projects/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: int, session: DBSession, current_user: CurrentUser
) -> ProjectResponse:
    project = await ProjectService(session).archive(project_id, current_user)
    return ProjectResponse.model_validate(project)
