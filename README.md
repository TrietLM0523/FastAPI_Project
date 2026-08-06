# TaskHub API

TaskHub is an asynchronous FastAPI backend for collaborative workspaces, projects,
tasks, labels, and comments. It includes JWT access/refresh authentication, layered
RBAC, Redis-backed project task-list caching, structured request tracing, and
background assignment notifications.

## Features

- User registration, login, access tokens, refresh-token rotation, logout, profile
  updates, and password changes.
- Global `ADMIN`/`USER` roles and workspace `OWNER`/`EDITOR`/`VIEWER` roles.
- Workspace membership, project CRUD/archive, task CRUD/assignment/status/filtering.
- Project-scoped Label CRUD and Task-Label attach/detach.
- Task comments with author-aware deletion rules.
- Redis async cache for filtered and paginated project task lists.
- Version-based cache invalidation after every task-response mutation.
- FastAPI background notification when an assignee changes to a user.
- JSON logs, `X-Request-ID`, normalized error responses, liveness/readiness checks.
- Swagger UI, ReDoc, async Alembic migrations, Ruff, Pytest, and Mypy support.

## Technology

- Python 3.11, FastAPI, Pydantic v2
- SQLAlchemy 2.x async, Alembic async
- SQLite + `aiosqlite` locally; PostgreSQL 16 in Docker Compose
- `redis.asyncio`, PyJWT, `pwdlib`/Argon2
- Pytest/pytest-asyncio/httpx, Ruff, Mypy

## Architecture

```text
app/
  api/            routers and FastAPI dependencies
  background/     notification contracts and logging sender
  cache/          Redis task-list cache and versioning
  core/           settings, security, logging, error handlers
  db/             async engine/session and declarative base
  middleware/     request ID and access logging
  models/         SQLAlchemy mappings
  repositories/   async SQLAlchemy queries
  schemas/        Pydantic request/response contracts
  services/       business rules, RBAC, transaction coordination
alembic/          async migrations
tests/            isolated SQLite and fake-Redis tests
```

Routers only handle HTTP contracts. Services authorize workflows and own transaction
boundaries. Repositories use SQLAlchemy 2.x async queries. Redis and notifications are
replaceable infrastructure abstractions.

## Permission model

| Actor | Read workspace resources | Create/update | Delete labels | Comments | Task status |
|---|---:|---:|---:|---:|---:|
| Global ADMIN | all | all | all | add/read/delete all | all |
| OWNER | own workspace | all active-project resources | yes | add/read/delete all | all |
| EDITOR | member workspace | projects/tasks/labels | yes | add/read/delete own | all task fields |
| VIEWER | member workspace | no | no | read only | assigned task status only |
| Non-member | no | no | no | no | no |

An assignee's status-only exception does not grant label or comment mutation rights.
Archived projects remain readable but every Task, Label, TaskLabel, and Comment
mutation is rejected.

## Data model

- `users` own workspaces, create/receive tasks, author comments, and hold refresh tokens.
- `workspaces` contain composite-key `workspace_members` and projects.
- `projects` contain tasks and labels and have `ACTIVE`/`ARCHIVED` status.
- `tasks` reference creator and optional assignee.
- `labels` are unique by `(project_id, normalized_name)`.
- `task_labels` has composite primary key `(task_id, label_id)`.
- `comments` reference their task and server-derived author.

Foreign keys use cascades so deleting a Label removes links, not Tasks. The service
layer additionally enforces that a Task and Label belong to the same Project.

## Local setup on Windows with Conda

```bat
conda env create -n fastapi_practice -f environment.yml
conda activate fastapi_practice
copy .env.example .env
```

Replace `JWT_SECRET_KEY` before any non-development run. A safe random value can be
generated with a password manager or Python's `secrets` module; never commit it.

Create the local data directory if needed and run migrations:

```bat
mkdir data
alembic upgrade head
```

Start the API:

```bat
python -m uvicorn app.main:app --reload
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Health: <http://127.0.0.1:8000/api/v1/health>
- Readiness: <http://127.0.0.1:8000/api/v1/health/ready>

The application never runs Alembic automatically during ordinary local startup.

## Redis locally

Set these values in `.env`:

```dotenv
REDIS_URL=redis://localhost:6379/0
CACHE_ENABLED=true
TASK_LIST_CACHE_TTL_SECONDS=60
CACHE_FAIL_FAST=false
```

Run Redis locally (native service, WSL, or Docker). When caching is disabled, TaskHub
bypasses Redis. When enabled but Redis is unavailable, the default behavior logs a
warning and serves the database result. Production can opt into startup failure with
`CACHE_FAIL_FAST=true`.

### Cache behavior

Only `GET /api/v1/projects/{project_id}/tasks` is cached. Authorization always runs
before cache lookup. Keys use:

```text
project:{project_id}:tasks:v{version}:{query_hash}
```

The hash includes normalized `status`, `priority`, `assignee_id`, `page`, and `limit`.
Task create/update/delete/status/assignment changes and Label attach/detach increment
the Project version. Updating or deleting a linked Label also invalidates the version.
Runtime code never uses Redis `KEYS`.

## Background assignment notifications

After a successful Task database commit, a new non-null assignee schedules a FastAPI
background job. Reassigning the same user or unassigning sends nothing. The development
sender writes non-secret assignment metadata to structured logs. Sender failure is
logged and cannot roll back the already committed Task. Real SMTP is intentionally out
of scope for Day 7.

## Tests and quality checks

Tests use a temporary SQLite database and fake async Redis; no developer database or
real Redis service is required.

```bat
pytest -v
ruff format --check .
ruff check .
mypy app
```

Migration round-trip check:

```bat
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

## Docker Compose

After copying `.env.example` to `.env`, change the database and Redis URLs for Compose:

```dotenv
DATABASE_URL=postgresql+asyncpg://taskhub:change-me@postgres:5432/taskhub
REDIS_URL=redis://redis:6379/0
POSTGRES_DB=taskhub
POSTGRES_USER=taskhub
POSTGRES_PASSWORD=change-me
```

Then run:

```bat
docker compose up --build
```

The Compose app waits for PostgreSQL and Redis health checks, runs
`alembic upgrade head`, and starts Uvicorn without reload.

## Swagger manual test flow

1. Authentication: `POST /auth/register`, `POST /auth/login`, copy `access_token`,
   click **Authorize**, then test refresh, `/auth/me`, and logout.
2. Workspace: create one, register another user, add them as `EDITOR`, change them to
   `VIEWER`, and verify mutation denial.
3. Project: create a Project and later archive it to verify read-only behavior.
4. Task: create, assign a member, change status, then test filters and pagination.
5. Label: create a Label, attach it to the Task, inspect Task detail, then detach it.
6. Comment: add a Comment, delete your own, and verify unauthorized deletion fails.
7. Cache: call the same task-list query twice, mutate the Task, and call again; inspect
   structured logs or automated cache tests.
8. Notification: assign a new user and inspect the background notification log.
9. Admin: use an ADMIN account created with `python -m scripts.create_admin` and verify
   global permission bypass.

## Main API routes

- `/api/v1/auth/*`, `/api/v1/users/*`
- `/api/v1/workspaces/*`, `/api/v1/projects/*`
- `/api/v1/projects/{project_id}/tasks`, `/api/v1/tasks/*`
- `/api/v1/projects/{project_id}/labels`, `/api/v1/labels/*`
- `/api/v1/tasks/{task_id}/labels/{label_id}`
- `/api/v1/tasks/{task_id}/comments`, `/api/v1/comments/{comment_id}`
- `/api/v1/health`, `/api/v1/health/live`, `/api/v1/health/ready`

## Development decisions and limitations

- Duplicate Task-Label attach returns `409`; detaching a missing link returns `404`.
- Label names are case-insensitively unique per Project and colors normalize to uppercase
  `#RRGGBB`.
- Comments support add/list/delete only; editing is intentionally omitted.
- Notifications use the logging backend only; SMTP, queues, Celery, WebSockets, frontend,
  OAuth, file upload, full-text search, Kubernetes, and production deployment are out of
  scope.
- SQLite timestamps do not provide PostgreSQL-level automatic `updated_at` triggers;
  SQLAlchemy updates them during ORM mutations.
