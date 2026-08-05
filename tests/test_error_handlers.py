from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.error_handlers import register_error_handlers
from app.middleware.request_context import RequestContextMiddleware
from app.services.exceptions import (
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)


async def test_service_error_handlers_map_expected_status_codes() -> None:
    app = FastAPI()

    @app.get("/not-found")
    async def not_found() -> None:
        raise NotFoundError("Task not found")

    @app.get("/forbidden")
    async def forbidden() -> None:
        raise ForbiddenError("No access")

    @app.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("Email exists")

    @app.get("/auth")
    async def auth_error() -> None:
        raise AuthenticationError("Bad credentials")

    @app.get("/validation")
    async def validation(value: int) -> None:
        return value

    register_error_handlers(app)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        not_found_response = await client.get("/not-found")
        forbidden_response = await client.get("/forbidden")
        conflict_response = await client.get("/conflict")
        auth_response = await client.get("/auth")
        validation_response = await client.get("/validation", params={"value": "bad"})

    assert not_found_response.status_code == 404
    assert not_found_response.json()["detail"] == "Task not found"
    assert not_found_response.json()["error_code"] == "not_found"

    assert forbidden_response.status_code == 403
    assert forbidden_response.json()["detail"] == "No access"
    assert forbidden_response.json()["error_code"] == "forbidden"

    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"] == "Email exists"
    assert conflict_response.json()["error_code"] == "conflict"

    assert auth_response.status_code == 401
    assert auth_response.json()["detail"] == "Bad credentials"
    assert auth_response.json()["error_code"] == "authentication"
    assert auth_response.headers["www-authenticate"] == "Bearer"

    assert validation_response.status_code == 422
    assert isinstance(validation_response.json()["detail"], list)
    assert validation_response.json()["error_code"] == "validation_error"


async def test_unexpected_exception_returns_safe_500() -> None:
    app = FastAPI()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret sql traceback")

    register_error_handlers(app)

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.json()["error_code"] == "internal_server_error"
    assert "secret sql traceback" not in response.text.lower()


async def test_unexpected_exception_keeps_request_id() -> None:
    app = FastAPI()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("private implementation detail")

    register_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/boom",
            headers={"X-Request-ID": "failure-trace"},
        )

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "failure-trace"
    assert response.json() == {
        "detail": "Internal server error",
        "error_code": "internal_server_error",
        "request_id": "failure-trace",
    }
    assert "private implementation detail" not in response.text
