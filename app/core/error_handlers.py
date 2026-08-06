import logging
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.exceptions import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    InactiveUserError,
    NotFoundError,
    ServiceError,
)

logger = logging.getLogger("app")


def _request_id(request: Request | None) -> str | None:
    if request is None:
        return None
    return getattr(getattr(request, "state", None), "request_id", None)


def _status_code_for_service_error(exc: ServiceError) -> int:
    if isinstance(exc, AuthenticationError):
        return 401
    if isinstance(exc, InactiveUserError):
        return 403
    if isinstance(exc, ForbiddenError):
        return 403
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, ConflictError):
        return 409
    return 500


def _error_code_for_status(status_code: int) -> str:
    mapping = {
        400: "bad_request",
        401: "authentication",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        500: "internal_server_error",
    }
    return mapping.get(status_code, "http_error")


def _render_error(
    *,
    request: Request | None,
    status_code: int,
    detail: Any,
    error_code: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {"detail": detail, "error_code": error_code}
    request_id = _request_id(request)
    if request_id is not None:
        payload["request_id"] = request_id
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        headers=headers,
    )


async def handle_service_error(request: Request, exc: ServiceError) -> JSONResponse:
    status_code = _status_code_for_service_error(exc)
    headers = None
    if isinstance(exc, AuthenticationError):
        headers = {"WWW-Authenticate": "Bearer"}
    return _render_error(
        request=request,
        status_code=status_code,
        detail=exc.message,
        error_code=exc.error_code,
        headers=headers,
    )


async def handle_http_exception(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return _render_error(
        request=request,
        status_code=exc.status_code,
        detail=exc.detail,
        error_code=_error_code_for_status(exc.status_code),
        headers=dict(exc.headers) if exc.headers else None,
    )


async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return _render_error(
        request=request,
        status_code=422,
        detail=exc.errors(),
        error_code="validation_error",
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled application exception",
        extra={"request_id": _request_id(request)},
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return _render_error(
        request=request,
        status_code=500,
        detail="Internal server error",
        error_code="internal_server_error",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ServiceError, cast(Any, handle_service_error))
    app.add_exception_handler(StarletteHTTPException, cast(Any, handle_http_exception))
    app.add_exception_handler(
        RequestValidationError, cast(Any, handle_validation_error)
    )
    app.add_exception_handler(Exception, handle_unexpected_error)
