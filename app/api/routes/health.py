import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.dependencies import DBSession

logger = logging.getLogger("app")

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Check application health",
)
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "message": "FastAPI application is running",
    }


@router.get(
    "/live",
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
)
async def health_live() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "api",
    }


@router.get(
    "/ready",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
)
async def health_ready(
    request: Request,
    session: DBSession,
) -> dict[str, object] | JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "Database readiness check failed",
            extra={"request_id": request_id},
        )
        payload: dict[str, object] = {
            "status": "not_ready",
            "checks": {"database": "down"},
        }
        if request_id is not None:
            payload["request_id"] = request_id
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload,
        )

    return {
        "status": "ready",
        "checks": {"database": "up"},
    }
