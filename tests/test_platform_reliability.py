import json
import logging

from httpx import AsyncClient
from pytest import MonkeyPatch, raises

from app.core.config import Settings
from app.core.logging import JsonFormatter, configure_logging
from app.db.session import get_db_session
from app.main import app
from tests.conftest import API_PREFIX
from tests.test_tasks import auth


async def test_request_id_is_generated_and_returned(client: AsyncClient) -> None:
    response = await client.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id
    assert isinstance(request_id, str)


async def test_client_request_id_is_preserved(client: AsyncClient) -> None:
    request_id = "trace-123"

    response = await client.get(
        f"{API_PREFIX}/health",
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id


async def test_error_responses_include_request_id(
    client: AsyncClient,
    register_user,
    login_user,
) -> None:
    await register_user(email="request-id@example.com")
    token = await login_user("request-id@example.com")

    response = await client.get(
        f"{API_PREFIX}/tasks/999",
        headers=auth(token),
    )

    assert response.status_code == 404
    assert response.headers["x-request-id"]
    assert response.json()["request_id"] == response.headers["x-request-id"]


async def test_health_endpoints_and_readiness(client: AsyncClient) -> None:
    live_response = await client.get(f"{API_PREFIX}/health/live")
    ready_response = await client.get(f"{API_PREFIX}/health/ready")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "healthy", "service": "api"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready", "checks": {"database": "up"}}


async def test_readiness_returns_503_when_db_fails(client: AsyncClient) -> None:
    class FailingSession:
        async def execute(self, _statement) -> None:
            raise RuntimeError("database unavailable")

    async def fail_db():
        yield FailingSession()

    original_override = app.dependency_overrides[get_db_session]
    app.dependency_overrides[get_db_session] = fail_db
    try:
        response = await client.get(f"{API_PREFIX}/health/ready")
    finally:
        app.dependency_overrides[get_db_session] = original_override

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"] == {"database": "down"}
    assert response.headers.get("x-request-id")


def test_settings_parse_and_production_secret_guard(
    monkeypatch: MonkeyPatch,
) -> None:
    development_settings = Settings(
        app_env=" DEVELOPMENT ",
        log_level=" info ",
        debug=True,
        _env_file=None,
    )
    assert development_settings.app_env == "development"
    assert development_settings.log_level == "INFO"

    monkeypatch.setenv("ALLOWED_HOSTS", " localhost, 127.0.0.1, ,test ")
    monkeypatch.setenv(
        "CORS_ORIGINS",
        " http://localhost:3000, http://127.0.0.1:3000, ",
    )
    parsed_settings = Settings(_env_file=None)

    assert parsed_settings.allowed_hosts == ["localhost", "127.0.0.1", "test"]
    assert parsed_settings.cors_origins == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    with raises(ValueError, match="non-default secret_key"):
        Settings(
            app_env="production",
            debug=False,
            secret_key="development-secret-key-change-me",
            _env_file=None,
        )


def test_json_formatter_contains_required_fields() -> None:
    record = logging.LogRecord(
        name="app.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request finished",
        args=(),
        exc_info=None,
    )
    record.request_id = "trace-456"
    record.method = "GET"
    record.path = "/api/v1/health"
    record.status_code = 200
    record.duration_ms = 18.2

    payload = json.loads(JsonFormatter().format(record))

    assert payload["logger"] == "app.access"
    assert payload["request_id"] == "trace-456"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/health"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 18.2


def test_configure_logging_does_not_duplicate_handlers() -> None:
    logger = configure_logging("INFO")
    handler_count = len(logger.handlers)

    configure_logging("DEBUG")
    configure_logging("INFO")

    assert len(logger.handlers) == handler_count
