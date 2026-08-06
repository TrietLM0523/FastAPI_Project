import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.cache.task_list import TaskListCache
from app.core.config import settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware

logger = logging.getLogger("app")

OPENAPI_TAGS = [
    {"name": "Authentication", "description": "Register, login, refresh, and logout."},
    {"name": "Users", "description": "Profiles, passwords, and admin user management."},
    {"name": "Workspaces", "description": "Workspace and membership management."},
    {"name": "Projects", "description": "Projects and archive lifecycle."},
    {"name": "Tasks", "description": "Task CRUD, assignment, filtering, and status."},
    {"name": "Labels", "description": "Project labels and task-label links."},
    {"name": "Comments", "description": "Task comments."},
    {"name": "Health", "description": "Liveness and database readiness."},
]


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    logger.info("Application startup")
    redis_client = None
    if settings.cache_enabled:
        try:
            from redis.asyncio import Redis

            redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
            await redis_client.ping()
            application.state.task_list_cache = TaskListCache(
                redis_client,
                enabled=True,
                ttl_seconds=settings.task_list_cache_ttl_seconds,
            )
            logger.info("Redis task-list cache is ready")
        except Exception:
            logger.warning(
                "Redis unavailable; task-list cache will use database fallback"
            )
            if redis_client is not None:
                await redis_client.aclose()
                redis_client = None
            if settings.app_env == "production" and settings.cache_fail_fast:
                raise
    try:
        yield
    finally:
        if redis_client is not None:
            await redis_client.aclose()
        logger.info("Application shutdown")


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    application = FastAPI(
        title=settings.app_name,
        description=settings.app_description,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
    )
    application.state.task_list_cache = TaskListCache(
        enabled=settings.cache_enabled,
        ttl_seconds=settings.task_list_cache_ttl_seconds,
    )

    if "*" in settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )
    else:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )
    # Added last so tracing wraps host/CORS responses as well as route responses.
    application.add_middleware(RequestContextMiddleware)

    register_error_handlers(application)
    application.include_router(api_router, prefix=settings.api_prefix)

    return application


app = create_app()
