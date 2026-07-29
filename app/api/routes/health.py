from fastapi import APIRouter, status

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
