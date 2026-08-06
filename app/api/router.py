from typing import Any

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.comments import router as comments_router
from app.api.routes.health import router as health_router
from app.api.routes.labels import router as labels_router
from app.api.routes.projects import router as projects_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.users import router as users_router
from app.api.routes.workspaces import router as workspaces_router

api_router = APIRouter()

PROTECTED_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, expired, or invalid bearer token"},
    403: {"description": "Insufficient workspace or global permission"},
    404: {"description": "Resource not found"},
    409: {"description": "Resource conflict or archived project mutation"},
    422: {"description": "Request validation failed"},
}

api_router.include_router(health_router)
api_router.include_router(
    auth_router,
    responses={
        401: PROTECTED_RESPONSES[401],
        409: PROTECTED_RESPONSES[409],
        422: PROTECTED_RESPONSES[422],
    },
)
api_router.include_router(users_router, responses=PROTECTED_RESPONSES)
api_router.include_router(workspaces_router, responses=PROTECTED_RESPONSES)
api_router.include_router(projects_router, responses=PROTECTED_RESPONSES)
api_router.include_router(tasks_router, responses=PROTECTED_RESPONSES)
api_router.include_router(labels_router, responses=PROTECTED_RESPONSES)
api_router.include_router(comments_router, responses=PROTECTED_RESPONSES)
