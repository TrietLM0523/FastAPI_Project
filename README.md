# FastAPI Practice

Project thực hành FastAPI theo từng ngày và quản lý thay đổi bằng GitHub Pull Request.

## Environment

- Windows
- Conda
- Python 3.11
- FastAPI

## Create environment

```bat
conda env create -f environment.yml
conda activate fastapi_practice
```

## Runtime configuration

Copy [.env.example](.env.example) to `.env` and adjust values for your environment.

Supported variables include:

- `APP_ENV` = `development` | `test` | `production`
- `DEBUG` = `true` or `false`
- `LOG_LEVEL` = `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL`
- `ALLOWED_HOSTS` = comma-separated host list
- `CORS_ORIGINS` = comma-separated allowed origins
- `DATABASE_URL`, `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

In production, the default development secret is rejected automatically to avoid unsafe deployments.

## Run application

```bat
python -m uvicorn app.main:app --reload
```

## API documentation

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- Health check: http://127.0.0.1:8000/api/v1/health
- Liveness: http://127.0.0.1:8000/api/v1/health/live
- Readiness: http://127.0.0.1:8000/api/v1/health/ready

## Liveness vs readiness

- Liveness checks whether the API process is alive and responsive. It never touches the database.
- Readiness checks whether the application can reach its database dependencies before serving traffic.

## X-Request-ID header

Each request receives an `X-Request-ID` response header. The header is read from inbound requests when present and otherwise generated as a UUID. The same ID is attached to structured access logs and centralized error responses for tracing.

## Health-check examples

```bat
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/health/live
curl http://127.0.0.1:8000/api/v1/health/ready
```

## Run tests

```bat
pytest -v
```

## Check code

```bat
ruff check .
ruff format --check .
```

## Format code

```bat
ruff format .
```
