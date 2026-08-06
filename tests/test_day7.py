from pathlib import Path

from httpx import AsyncClient
from pydantic import ValidationError
from pytest import MonkeyPatch, raises
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_notification_sender
from app.background.notifications import AssignmentNotification
from app.cache.task_list import TaskListCache
from app.core.config import Settings
from app.main import app
from app.repositories.task import TaskRepository
from tests.conftest import API_PREFIX
from tests.test_taskhub import add_member, auth, create_project, create_workspace


class FakeRedis:
    def __init__(self, *, failing: bool = False) -> None:
        self.values: dict[str, str] = {}
        self.failing = failing
        self.get_calls: list[str] = []

    async def get(self, key: str) -> str | None:
        self.get_calls.append(key)
        if self.failing:
            raise ConnectionError("redis unavailable")
        return self.values.get(key)

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        if self.failing:
            raise ConnectionError("redis unavailable")
        self.values[key] = value

    async def incr(self, key: str) -> int:
        if self.failing:
            raise ConnectionError("redis unavailable")
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value


class RecordingSender:
    def __init__(self, *, failing: bool = False) -> None:
        self.notifications: list[AssignmentNotification] = []
        self.failing = failing

    async def send_assignment(self, notification: AssignmentNotification) -> None:
        self.notifications.append(notification)
        if self.failing:
            raise RuntimeError("mail provider rejected request")


async def day7_context(
    client: AsyncClient, register_user, login_user
) -> dict[str, object]:
    owner = await register_user(email="day7-owner@example.com")
    editor = await register_user(email="day7-editor@example.com")
    viewer = await register_user(email="day7-viewer@example.com")
    outsider = await register_user(email="day7-outsider@example.com")
    owner_token = await login_user(owner["email"])
    editor_token = await login_user(editor["email"])
    viewer_token = await login_user(viewer["email"])
    outsider_token = await login_user(outsider["email"])
    workspace = await create_workspace(client, owner_token, "Day 7 Workspace")
    await add_member(client, owner_token, workspace["id"], editor["email"], "EDITOR")
    await add_member(client, owner_token, workspace["id"], viewer["email"], "VIEWER")
    project = await create_project(client, owner_token, workspace["id"], "Day 7")
    return {
        "owner": owner,
        "editor": editor,
        "viewer": viewer,
        "outsider": outsider,
        "owner_token": owner_token,
        "editor_token": editor_token,
        "viewer_token": viewer_token,
        "outsider_token": outsider_token,
        "workspace": workspace,
        "project": project,
    }


async def create_task(
    client: AsyncClient, project_id: int, token: str, title: str = "Day 7 task"
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/projects/{project_id}/tasks",
        json={"title": title},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_label(
    client: AsyncClient,
    project_id: int,
    token: str,
    name: str = "Backend",
    color: str = "#ff5733",
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/projects/{project_id}/labels",
        json={"name": name, "color": color},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_label_crud_permissions_uniqueness_and_validation(
    client: AsyncClient, register_user, login_user
) -> None:
    context = await day7_context(client, register_user, login_user)
    project = context["project"]
    owner_token = context["owner_token"]
    editor_token = context["editor_token"]
    viewer_token = context["viewer_token"]
    outsider_token = context["outsider_token"]
    workspace = context["workspace"]
    assert isinstance(project, dict)
    assert isinstance(workspace, dict)
    assert all(
        isinstance(token, str)
        for token in (owner_token, editor_token, viewer_token, outsider_token)
    )

    owner_label = await create_label(client, project["id"], owner_token)
    assert owner_label["color"] == "#FF5733"
    editor_label = await create_label(
        client, project["id"], editor_token, "Frontend", "#123abc"
    )
    assert editor_label["color"] == "#123ABC"

    viewer_create = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/labels",
        json={"name": "Denied", "color": "#000000"},
        headers=auth(viewer_token),
    )
    assert viewer_create.status_code == 403
    outsider_list = await client.get(
        f"{API_PREFIX}/projects/{project['id']}/labels",
        headers=auth(outsider_token),
    )
    assert outsider_list.status_code == 403

    duplicate = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/labels",
        json={"name": "  backend  ", "color": "#FFFFFF"},
        headers=auth(owner_token),
    )
    assert duplicate.status_code == 409
    invalid = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/labels",
        json={"name": "Invalid", "color": "red"},
        headers=auth(owner_token),
    )
    assert invalid.status_code == 422

    second_project = await create_project(
        client, owner_token, workspace["id"], "Second project"
    )
    same_name = await create_label(client, second_project["id"], owner_token, "BACKEND")
    assert same_name["project_id"] == second_project["id"]

    listed = await client.get(
        f"{API_PREFIX}/projects/{project['id']}/labels",
        headers=auth(viewer_token),
    )
    assert listed.status_code == 200
    assert {item["name"] for item in listed.json()} == {"Backend", "Frontend"}
    updated = await client.patch(
        f"{API_PREFIX}/labels/{editor_label['id']}",
        json={"name": "UI", "color": "#abcdef"},
        headers=auth(editor_token),
    )
    assert updated.status_code == 200
    assert updated.json()["color"] == "#ABCDEF"


async def test_task_label_attach_detach_cross_project_and_delete_safety(
    client: AsyncClient, register_user, login_user
) -> None:
    context = await day7_context(client, register_user, login_user)
    project = context["project"]
    workspace = context["workspace"]
    owner_token = context["owner_token"]
    viewer_token = context["viewer_token"]
    assert isinstance(project, dict) and isinstance(workspace, dict)
    assert isinstance(owner_token, str) and isinstance(viewer_token, str)
    task = await create_task(client, project["id"], owner_token)
    label = await create_label(client, project["id"], owner_token)

    attach_url = f"{API_PREFIX}/tasks/{task['id']}/labels/{label['id']}"
    denied = await client.post(attach_url, headers=auth(viewer_token))
    assert denied.status_code == 403
    attached = await client.post(attach_url, headers=auth(owner_token))
    assert attached.status_code == 204
    duplicate = await client.post(attach_url, headers=auth(owner_token))
    assert duplicate.status_code == 409
    detail = await client.get(
        f"{API_PREFIX}/tasks/{task['id']}", headers=auth(owner_token)
    )
    assert detail.json()["labels"][0]["id"] == label["id"]

    second_project = await create_project(
        client, owner_token, workspace["id"], "Cross-project"
    )
    other_label = await create_label(client, second_project["id"], owner_token, "Other")
    cross = await client.post(
        f"{API_PREFIX}/tasks/{task['id']}/labels/{other_label['id']}",
        headers=auth(owner_token),
    )
    assert cross.status_code == 409

    detached = await client.delete(attach_url, headers=auth(owner_token))
    assert detached.status_code == 204
    missing = await client.delete(attach_url, headers=auth(owner_token))
    assert missing.status_code == 404
    await client.post(attach_url, headers=auth(owner_token))
    deleted = await client.delete(
        f"{API_PREFIX}/labels/{label['id']}", headers=auth(owner_token)
    )
    assert deleted.status_code == 204
    task_still_exists = await client.get(
        f"{API_PREFIX}/tasks/{task['id']}", headers=auth(owner_token)
    )
    assert task_still_exists.status_code == 200
    assert task_still_exists.json()["labels"] == []


async def test_comment_permissions_content_and_author_identity(
    client: AsyncClient, register_user, login_user, make_admin
) -> None:
    context = await day7_context(client, register_user, login_user)
    project = context["project"]
    owner = context["owner"]
    editor = context["editor"]
    owner_token = context["owner_token"]
    editor_token = context["editor_token"]
    viewer_token = context["viewer_token"]
    outsider_token = context["outsider_token"]
    assert isinstance(project, dict)
    assert isinstance(owner, dict)
    assert isinstance(editor, dict)
    assert all(
        isinstance(token, str)
        for token in (owner_token, editor_token, viewer_token, outsider_token)
    )
    task = await create_task(client, project["id"], owner_token)
    url = f"{API_PREFIX}/tasks/{task['id']}/comments"

    owner_comment = await client.post(
        url, json={"content": "  Owner note  "}, headers=auth(owner_token)
    )
    assert owner_comment.status_code == 201
    assert owner_comment.json()["author_id"] == owner["id"]
    assert owner_comment.json()["content"] == "Owner note"
    editor_comment = await client.post(
        url, json={"content": "Editor note"}, headers=auth(editor_token)
    )
    assert editor_comment.status_code == 201
    assert editor_comment.json()["author_id"] == editor["id"]
    spoof = await client.post(
        url,
        json={"content": "Spoof", "author_id": owner["id"]},
        headers=auth(editor_token),
    )
    assert spoof.status_code == 422
    empty = await client.post(url, json={"content": "  "}, headers=auth(owner_token))
    assert empty.status_code == 422
    viewer_create = await client.post(
        url, json={"content": "Denied"}, headers=auth(viewer_token)
    )
    assert viewer_create.status_code == 403
    outsider_list = await client.get(url, headers=auth(outsider_token))
    assert outsider_list.status_code == 403
    viewer_list = await client.get(url, headers=auth(viewer_token))
    assert viewer_list.status_code == 200
    assert len(viewer_list.json()) == 2

    editor_delete_other = await client.delete(
        f"{API_PREFIX}/comments/{owner_comment.json()['id']}",
        headers=auth(editor_token),
    )
    assert editor_delete_other.status_code == 403
    editor_delete_own = await client.delete(
        f"{API_PREFIX}/comments/{editor_comment.json()['id']}",
        headers=auth(editor_token),
    )
    assert editor_delete_own.status_code == 204
    owner_delete = await client.delete(
        f"{API_PREFIX}/comments/{owner_comment.json()['id']}",
        headers=auth(owner_token),
    )
    assert owner_delete.status_code == 204

    admin = await make_admin()
    admin_token_response = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": admin.email, "password": "AdminPassword123!"},
    )
    admin_token = admin_token_response.json()["access_token"]
    admin_comment = await client.post(
        url, json={"content": "Admin"}, headers=auth(admin_token)
    )
    assert admin_comment.status_code == 201
    admin_delete = await client.delete(
        f"{API_PREFIX}/comments/{admin_comment.json()['id']}",
        headers=auth(admin_token),
    )
    assert admin_delete.status_code == 204


async def test_archived_project_is_read_only_for_day7_resources(
    client: AsyncClient, register_user, login_user
) -> None:
    context = await day7_context(client, register_user, login_user)
    project = context["project"]
    owner_token = context["owner_token"]
    assert isinstance(project, dict) and isinstance(owner_token, str)
    task = await create_task(client, project["id"], owner_token)
    label = await create_label(client, project["id"], owner_token)
    comment = await client.post(
        f"{API_PREFIX}/tasks/{task['id']}/comments",
        json={"content": "Before archive"},
        headers=auth(owner_token),
    )
    archived = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/archive", headers=auth(owner_token)
    )
    assert archived.status_code == 200
    for response in (
        await client.post(
            f"{API_PREFIX}/projects/{project['id']}/labels",
            json={"name": "Late", "color": "#000000"},
            headers=auth(owner_token),
        ),
        await client.patch(
            f"{API_PREFIX}/labels/{label['id']}",
            json={"name": "Late"},
            headers=auth(owner_token),
        ),
        await client.post(
            f"{API_PREFIX}/tasks/{task['id']}/labels/{label['id']}",
            headers=auth(owner_token),
        ),
        await client.post(
            f"{API_PREFIX}/tasks/{task['id']}/comments",
            json={"content": "Late"},
            headers=auth(owner_token),
        ),
        await client.delete(
            f"{API_PREFIX}/comments/{comment.json()['id']}",
            headers=auth(owner_token),
        ),
    ):
        assert response.status_code == 409
    assert (
        await client.get(
            f"{API_PREFIX}/projects/{project['id']}/labels",
            headers=auth(owner_token),
        )
    ).status_code == 200
    assert (
        await client.get(
            f"{API_PREFIX}/tasks/{task['id']}/comments",
            headers=auth(owner_token),
        )
    ).status_code == 200


async def test_task_list_cache_hit_keys_invalidation_and_fallback(
    client: AsyncClient,
    register_user,
    login_user,
    monkeypatch: MonkeyPatch,
) -> None:
    fake = FakeRedis()
    app.state.task_list_cache = TaskListCache(fake, enabled=True, ttl_seconds=60)
    context = await day7_context(client, register_user, login_user)
    project = context["project"]
    owner_token = context["owner_token"]
    outsider_token = context["outsider_token"]
    assert isinstance(project, dict)
    assert isinstance(owner_token, str) and isinstance(outsider_token, str)
    await create_task(client, project["id"], owner_token)
    version_key = TaskListCache.version_key(project["id"])
    assert fake.values[version_key] == "1"

    list_url = f"{API_PREFIX}/projects/{project['id']}/tasks"
    first = await client.get(list_url, headers=auth(owner_token))
    assert first.status_code == 200

    async def repository_must_not_run(*_args, **_kwargs):
        raise AssertionError("cache hit queried task repository")

    monkeypatch.setattr(
        TaskRepository, "list_by_project_filtered", repository_must_not_run
    )
    second = await client.get(list_url, headers=auth(owner_token))
    assert second.status_code == 200
    assert second.json() == first.json()
    unauthorized = await client.get(list_url, headers=auth(outsider_token))
    assert unauthorized.status_code == 403

    base_hash = TaskListCache.query_hash({"page": 1, "limit": 20})
    filter_hash = TaskListCache.query_hash({"page": 1, "limit": 20, "status": "TODO"})
    page_hash = TaskListCache.query_hash({"page": 2, "limit": 20})
    assert len({base_hash, filter_hash, page_hash}) == 3

    monkeypatch.undo()
    update = await client.patch(
        f"{API_PREFIX}/tasks/{first.json()['items'][0]['id']}",
        json={"priority": "HIGH"},
        headers=auth(owner_token),
    )
    assert update.status_code == 200
    assert fake.values[version_key] == "2"
    refreshed = await client.get(list_url, headers=auth(owner_token))
    assert refreshed.json()["items"][0]["priority"] == "HIGH"

    task_id = first.json()["items"][0]["id"]
    status_update = await client.patch(
        f"{API_PREFIX}/tasks/{task_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth(owner_token),
    )
    assert status_update.status_code == 200
    assert fake.values[version_key] == "3"
    editor = context["editor"]
    assert isinstance(editor, dict)
    assignment = await client.patch(
        f"{API_PREFIX}/tasks/{task_id}",
        json={"assignee_id": editor["id"]},
        headers=auth(owner_token),
    )
    assert assignment.status_code == 200
    assert fake.values[version_key] == "4"
    label = await create_label(client, project["id"], owner_token, "Cached")
    link_url = f"{API_PREFIX}/tasks/{task_id}/labels/{label['id']}"
    assert (await client.post(link_url, headers=auth(owner_token))).status_code == 204
    assert fake.values[version_key] == "5"
    assert (await client.delete(link_url, headers=auth(owner_token))).status_code == 204
    assert fake.values[version_key] == "6"

    failing_cache = TaskListCache(FakeRedis(failing=True), enabled=True)
    app.state.task_list_cache = failing_cache
    fallback = await client.get(list_url, headers=auth(owner_token))
    assert fallback.status_code == 200
    assert fallback.json()["total"] == 1
    app.state.task_list_cache = TaskListCache(enabled=False)


async def test_assignment_notifications_are_change_aware_and_failure_safe(
    client: AsyncClient,
    register_user,
    login_user,
    monkeypatch: MonkeyPatch,
) -> None:
    sender = RecordingSender()
    app.dependency_overrides[get_notification_sender] = lambda: sender
    context = await day7_context(client, register_user, login_user)
    project = context["project"]
    editor = context["editor"]
    owner_token = context["owner_token"]
    assert isinstance(project, dict) and isinstance(editor, dict)
    assert isinstance(owner_token, str)
    created = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={"title": "Notify", "assignee_id": editor["id"]},
        headers=auth(owner_token),
    )
    assert created.status_code == 201
    assert len(sender.notifications) == 1
    notification = sender.notifications[0]
    assert notification.assignee_email == editor["email"]
    assert notification.task_title == "Notify"
    assert notification.project_name == "Day 7"

    same = await client.patch(
        f"{API_PREFIX}/tasks/{created.json()['id']}",
        json={"assignee_id": editor["id"]},
        headers=auth(owner_token),
    )
    assert same.status_code == 200
    unassign = await client.patch(
        f"{API_PREFIX}/tasks/{created.json()['id']}",
        json={"assignee_id": None},
        headers=auth(owner_token),
    )
    assert unassign.status_code == 200
    assert len(sender.notifications) == 1

    failing_sender = RecordingSender(failing=True)
    app.dependency_overrides[get_notification_sender] = lambda: failing_sender
    failure_safe = await client.patch(
        f"{API_PREFIX}/tasks/{created.json()['id']}",
        json={"assignee_id": editor["id"]},
        headers=auth(owner_token),
    )
    assert failure_safe.status_code == 200
    persisted = await client.get(
        f"{API_PREFIX}/tasks/{created.json()['id']}", headers=auth(owner_token)
    )
    assert persisted.json()["assignee_id"] == editor["id"]
    assert len(failing_sender.notifications) == 1

    app.dependency_overrides[get_notification_sender] = lambda: sender
    original_commit = AsyncSession.commit

    async def failing_commit(_session: AsyncSession) -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    failed_transaction = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={"title": "Must not notify", "assignee_id": editor["id"]},
        headers=auth(owner_token),
    )
    assert failed_transaction.status_code == 500
    assert len(sender.notifications) == 1
    monkeypatch.setattr(AsyncSession, "commit", original_commit)


def test_openapi_and_settings_cover_day7_contract() -> None:
    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
    tags = {
        operation["tags"][0]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and operation.get("tags")
    }
    assert {"Authentication", "Users", "Workspaces", "Projects", "Tasks"} <= tags
    assert {"Labels", "Comments", "Health"} <= tags
    assert "/api/v1/projects/{project_id}/labels" in schema["paths"]
    assert "/api/v1/tasks/{task_id}/comments" in schema["paths"]
    label_responses = schema["paths"]["/api/v1/projects/{project_id}/labels"]["post"][
        "responses"
    ]
    assert {"401", "403", "404", "409", "422"} <= set(label_responses)

    settings = Settings(
        api_v1_prefix="/custom",
        jwt_secret_key="x" * 32,
        backend_cors_origins="http://localhost:3000",
        cache_enabled=False,
        _env_file=None,
    )
    assert settings.api_prefix == "/custom"
    assert settings.secret_key == "x" * 32
    assert settings.cors_origins == ["http://localhost:3000"]
    with raises(ValidationError):
        Settings(access_token_expire_minutes=0, _env_file=None)
    with raises(ValidationError):
        Settings(jwt_secret_key="short", _env_file=None)
    with raises(ValidationError):
        Settings(database_url="", _env_file=None)
    with raises(ValidationError):
        Settings(refresh_token_expire_days=0, _env_file=None)

    example_env = Path(".env.example").read_text(encoding="utf-8")
    assert "JWT_SECRET_KEY=development-secret-key-change-me" in example_env
    assert "REDIS_URL=redis://localhost:6379/0" in example_env
    assert "JWT_SECRET_KEY=sk-" not in example_env
