from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.user import User
from app.models.workspace import Workspace
from app.repositories.workspace import WorkspaceMemberRepository
from app.schemas.workspace import WorkspaceCreate
from app.services.workspace import WorkspaceService
from tests.conftest import API_PREFIX


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_workspace(client: AsyncClient, token: str, name: str = "Team") -> dict:
    response = await client.post(
        f"{API_PREFIX}/workspaces", json={"name": name}, headers=auth(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_member(
    client: AsyncClient, owner_token: str, workspace_id: int, email: str, role: str
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/workspaces/{workspace_id}/members",
        json={"email": email, "role": role},
        headers=auth(owner_token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_project(
    client: AsyncClient, token: str, workspace_id: int, name: str = "Project"
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/workspaces/{workspace_id}/projects",
        json={"name": name, "description": "Details"},
        headers=auth(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_workspace_creation_is_atomic_and_creates_owner_membership(
    client: AsyncClient, register_user, login_user, session_factory, monkeypatch
) -> None:
    owner = await register_user(email="workspace-owner@example.com")
    token = await login_user("workspace-owner@example.com")
    workspace = await create_workspace(client, token, "  Product  ")
    assert workspace["name"] == "Product"
    assert workspace["owner_id"] == owner["id"]

    members_response = await client.get(
        f"{API_PREFIX}/workspaces/{workspace['id']}/members", headers=auth(token)
    )
    assert members_response.status_code == 200
    assert members_response.json()[0]["role"] == "OWNER"
    assert members_response.json()[0]["user"]["email"] == owner["email"]

    async def fail_add(*_args, **_kwargs):
        raise RuntimeError("membership failure")

    monkeypatch.setattr(WorkspaceMemberRepository, "add_member", fail_add)
    async with session_factory() as session:
        try:
            actor = await session.get(User, owner["id"])
            assert actor is not None
            await WorkspaceService(session).create(
                WorkspaceCreate(name="Must Roll Back"),
                actor,
            )
        except RuntimeError:
            pass
        count = await session.scalar(
            select(func.count())
            .select_from(Workspace)
            .where(Workspace.name == "Must Roll Back")
        )
        assert count == 0

    null_update = await client.patch(
        f"{API_PREFIX}/workspaces/{workspace['id']}",
        json={"name": None},
        headers=auth(token),
    )
    assert null_update.status_code == 422
    update_response = await client.patch(
        f"{API_PREFIX}/workspaces/{workspace['id']}",
        json={"name": "Renamed"},
        headers=auth(token),
    )
    assert update_response.status_code == 200
    delete_response = await client.delete(
        f"{API_PREFIX}/workspaces/{workspace['id']}", headers=auth(token)
    )
    assert delete_response.status_code == 204


async def test_workspace_membership_roles_and_visibility(
    client: AsyncClient, register_user, login_user, make_admin
) -> None:
    owner = await register_user(email="owner-rbac@example.com")
    editor = await register_user(email="editor-rbac@example.com")
    viewer = await register_user(email="viewer-rbac@example.com")
    outsider = await register_user(email="outsider-rbac@example.com")
    owner_token = await login_user(owner["email"])
    editor_token = await login_user(editor["email"])
    viewer_token = await login_user(viewer["email"])
    outsider_token = await login_user(outsider["email"])
    workspace = await create_workspace(client, owner_token)

    await add_member(client, owner_token, workspace["id"], editor["email"], "EDITOR")
    await add_member(client, owner_token, workspace["id"], viewer["email"], "VIEWER")
    duplicate = await client.post(
        f"{API_PREFIX}/workspaces/{workspace['id']}/members",
        json={"email": editor["email"], "role": "EDITOR"},
        headers=auth(owner_token),
    )
    assert duplicate.status_code == 409
    unknown_user = await client.post(
        f"{API_PREFIX}/workspaces/{workspace['id']}/members",
        json={"email": "missing@example.com", "role": "VIEWER"},
        headers=auth(owner_token),
    )
    assert unknown_user.status_code == 404

    for token in (editor_token, viewer_token):
        forbidden = await client.post(
            f"{API_PREFIX}/workspaces/{workspace['id']}/members",
            json={"email": outsider["email"], "role": "VIEWER"},
            headers=auth(token),
        )
        assert forbidden.status_code == 403

    outsider_read = await client.get(
        f"{API_PREFIX}/workspaces/{workspace['id']}", headers=auth(outsider_token)
    )
    assert outsider_read.status_code == 403
    outsider_list = await client.get(
        f"{API_PREFIX}/workspaces", headers=auth(outsider_token)
    )
    assert outsider_list.status_code == 200
    assert outsider_list.json()["total"] == 0
    editor_list = await client.get(
        f"{API_PREFIX}/workspaces", headers=auth(editor_token)
    )
    assert editor_list.json()["total"] == 1
    for token in (editor_token, viewer_token):
        denied_update = await client.patch(
            f"{API_PREFIX}/workspaces/{workspace['id']}",
            json={"name": "Denied"},
            headers=auth(token),
        )
        assert denied_update.status_code == 403
    missing = await client.get(
        f"{API_PREFIX}/workspaces/99999", headers=auth(outsider_token)
    )
    assert missing.status_code == 404

    role_change = await client.patch(
        f"{API_PREFIX}/workspaces/{workspace['id']}/members/{editor['id']}",
        json={"role": "VIEWER"},
        headers=auth(owner_token),
    )
    assert role_change.status_code == 200
    assert role_change.json()["role"] == "VIEWER"
    remove_owner = await client.delete(
        f"{API_PREFIX}/workspaces/{workspace['id']}/members/{owner['id']}",
        headers=auth(owner_token),
    )
    assert remove_owner.status_code == 403
    remove_viewer = await client.delete(
        f"{API_PREFIX}/workspaces/{workspace['id']}/members/{viewer['id']}",
        headers=auth(owner_token),
    )
    assert remove_viewer.status_code == 204

    await make_admin()
    admin_token = await login_user("admin@example.com", "AdminPassword123!")
    admin_read = await client.get(
        f"{API_PREFIX}/workspaces/{workspace['id']}", headers=auth(admin_token)
    )
    assert admin_read.status_code == 200
    admin_list = await client.get(f"{API_PREFIX}/workspaces", headers=auth(admin_token))
    assert admin_list.json()["total"] == 1


async def test_project_permissions_and_archive_read_only(
    client: AsyncClient, register_user, login_user
) -> None:
    owner = await register_user(email="project-owner@example.com")
    editor = await register_user(email="project-editor@example.com")
    viewer = await register_user(email="project-viewer@example.com")
    outsider = await register_user(email="project-outsider@example.com")
    owner_token = await login_user(owner["email"])
    editor_token = await login_user(editor["email"])
    viewer_token = await login_user(viewer["email"])
    outsider_token = await login_user(outsider["email"])
    workspace = await create_workspace(client, owner_token)
    await add_member(client, owner_token, workspace["id"], editor["email"], "EDITOR")
    await add_member(client, owner_token, workspace["id"], viewer["email"], "VIEWER")

    project = await create_project(client, editor_token, workspace["id"])
    task_before_archive = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={"title": "Existing"},
        headers=auth(owner_token),
    )
    assert task_before_archive.status_code == 201
    viewer_create = await client.post(
        f"{API_PREFIX}/workspaces/{workspace['id']}/projects",
        json={"name": "Denied"},
        headers=auth(viewer_token),
    )
    assert viewer_create.status_code == 403
    outsider_create = await client.post(
        f"{API_PREFIX}/workspaces/{workspace['id']}/projects",
        json={"name": "Denied"},
        headers=auth(outsider_token),
    )
    assert outsider_create.status_code == 403
    viewer_read = await client.get(
        f"{API_PREFIX}/projects/{project['id']}", headers=auth(viewer_token)
    )
    assert viewer_read.status_code == 200
    viewer_update = await client.patch(
        f"{API_PREFIX}/projects/{project['id']}",
        json={"name": "Denied"},
        headers=auth(viewer_token),
    )
    assert viewer_update.status_code == 403
    viewer_archive = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/archive",
        headers=auth(viewer_token),
    )
    assert viewer_archive.status_code == 403
    update = await client.patch(
        f"{API_PREFIX}/projects/{project['id']}",
        json={"description": None},
        headers=auth(editor_token),
    )
    assert update.status_code == 200
    archive = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/archive", headers=auth(editor_token)
    )
    assert archive.status_code == 200
    assert archive.json()["status"] == "ARCHIVED"
    archived_read = await client.get(
        f"{API_PREFIX}/projects/{project['id']}", headers=auth(viewer_token)
    )
    assert archived_read.status_code == 200
    create_task_response = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={"title": "Denied"},
        headers=auth(owner_token),
    )
    assert create_task_response.status_code == 409
    for method in ("patch", "delete"):
        request = getattr(client, method)
        kwargs = {"json": {"title": "Denied"}} if method == "patch" else {}
        response = await request(
            f"{API_PREFIX}/tasks/{task_before_archive.json()['id']}",
            headers=auth(owner_token),
            **kwargs,
        )
        assert response.status_code == 409


async def test_task_rbac_assignment_and_assignee_status_only(
    client: AsyncClient, register_user, login_user
) -> None:
    owner = await register_user(email="taskhub-owner@example.com")
    editor = await register_user(email="taskhub-editor@example.com")
    viewer = await register_user(email="taskhub-viewer@example.com")
    outsider = await register_user(email="taskhub-outsider@example.com")
    owner_token = await login_user(owner["email"])
    editor_token = await login_user(editor["email"])
    viewer_token = await login_user(viewer["email"])
    outsider_token = await login_user(outsider["email"])
    workspace = await create_workspace(client, owner_token)
    await add_member(client, owner_token, workspace["id"], editor["email"], "EDITOR")
    await add_member(client, owner_token, workspace["id"], viewer["email"], "VIEWER")
    project = await create_project(client, owner_token, workspace["id"])

    task_response = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={
            "title": "Assigned",
            "assignee_id": viewer["id"],
            "priority": "HIGH",
            "due_date": "2026-08-20",
        },
        headers=auth(editor_token),
    )
    assert task_response.status_code == 201, task_response.text
    task = task_response.json()
    assert task["created_by"] == editor["id"]
    assert task["project_id"] == project["id"]

    invalid_assignment = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={"title": "Bad", "assignee_id": outsider["id"]},
        headers=auth(owner_token),
    )
    assert invalid_assignment.status_code == 403
    viewer_create = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={"title": "Viewer denied"},
        headers=auth(viewer_token),
    )
    assert viewer_create.status_code == 403
    viewer_status = await client.patch(
        f"{API_PREFIX}/tasks/{task['id']}/status",
        json={"status": "IN_PROGRESS"},
        headers=auth(viewer_token),
    )
    assert viewer_status.status_code == 200
    viewer_other_field = await client.patch(
        f"{API_PREFIX}/tasks/{task['id']}",
        json={"status": "DONE", "title": "Escalation"},
        headers=auth(viewer_token),
    )
    assert viewer_other_field.status_code == 403
    owner_update = await client.patch(
        f"{API_PREFIX}/tasks/{task['id']}",
        json={"priority": "URGENT", "assignee_id": None},
        headers=auth(owner_token),
    )
    assert owner_update.status_code == 200
    assert owner_update.json()["priority"] == "URGENT"
    outsider_read = await client.get(
        f"{API_PREFIX}/tasks/{task['id']}", headers=auth(outsider_token)
    )
    assert outsider_read.status_code == 403

    owner_delete = await client.delete(
        f"{API_PREFIX}/tasks/{task['id']}", headers=auth(owner_token)
    )
    assert owner_delete.status_code == 204


async def test_editor_only_deletes_own_task_and_task_filter_pagination(
    client: AsyncClient, register_user, login_user
) -> None:
    owner = await register_user(email="filter-owner@example.com")
    editor = await register_user(email="filter-editor@example.com")
    owner_token = await login_user(owner["email"])
    editor_token = await login_user(editor["email"])
    workspace = await create_workspace(client, owner_token)
    await add_member(client, owner_token, workspace["id"], editor["email"], "EDITOR")
    project = await create_project(client, owner_token, workspace["id"])

    payloads = [
        {
            "title": "A",
            "status": "TODO",
            "priority": "HIGH",
            "assignee_id": editor["id"],
        },
        {
            "title": "B",
            "status": "TODO",
            "priority": "LOW",
            "assignee_id": editor["id"],
        },
        {"title": "C", "status": "DONE", "priority": "HIGH"},
    ]
    created = []
    for payload in payloads:
        response = await client.post(
            f"{API_PREFIX}/projects/{project['id']}/tasks",
            json=payload,
            headers=auth(owner_token),
        )
        assert response.status_code == 201
        created.append(response.json())

    combined = await client.get(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        params={
            "status": "TODO",
            "priority": "HIGH",
            "assignee_id": editor["id"],
            "page": 1,
            "limit": 1,
        },
        headers=auth(editor_token),
    )
    assert combined.status_code == 200
    assert combined.json()["total"] == 1
    assert combined.json()["pages"] == 1
    assert combined.json()["items"][0]["title"] == "A"
    filter_expectations = (
        ({"status": "TODO"}, 2),
        ({"priority": "HIGH"}, 2),
        ({"assignee_id": editor["id"]}, 2),
    )
    for params, expected_total in filter_expectations:
        response = await client.get(
            f"{API_PREFIX}/projects/{project['id']}/tasks",
            params=params,
            headers=auth(owner_token),
        )
        assert response.status_code == 200
        assert response.json()["total"] == expected_total
    second_page = await client.get(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        params={"page": 2, "limit": 2},
        headers=auth(owner_token),
    )
    assert second_page.status_code == 200
    assert second_page.json()["total"] == 3
    assert second_page.json()["pages"] == 2
    assert [item["title"] for item in second_page.json()["items"]] == ["C"]
    invalid_limit = await client.get(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        params={"limit": 101},
        headers=auth(owner_token),
    )
    assert invalid_limit.status_code == 422

    editor_update_other = await client.patch(
        f"{API_PREFIX}/tasks/{created[0]['id']}",
        json={"description": "Editor may update"},
        headers=auth(editor_token),
    )
    assert editor_update_other.status_code == 200

    editor_delete_other = await client.delete(
        f"{API_PREFIX}/tasks/{created[0]['id']}", headers=auth(editor_token)
    )
    assert editor_delete_other.status_code == 403
    own_task = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={"title": "Editor task"},
        headers=auth(editor_token),
    )
    editor_delete_own = await client.delete(
        f"{API_PREFIX}/tasks/{own_task.json()['id']}", headers=auth(editor_token)
    )
    assert editor_delete_own.status_code == 204


async def test_admin_bypasses_workspace_roles_for_project_and_task_management(
    client: AsyncClient, register_user, login_user, make_admin
) -> None:
    owner = await register_user(email="admin-bypass-owner@example.com")
    owner_token = await login_user(owner["email"])
    workspace = await create_workspace(client, owner_token)
    await make_admin()
    admin_token = await login_user("admin@example.com", "AdminPassword123!")

    project = await create_project(client, admin_token, workspace["id"], "Admin")
    task_response = await client.post(
        f"{API_PREFIX}/projects/{project['id']}/tasks",
        json={"title": "Admin task", "assignee_id": owner["id"]},
        headers=auth(admin_token),
    )
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]
    update_response = await client.patch(
        f"{API_PREFIX}/tasks/{task_id}",
        json={"status": "DONE"},
        headers=auth(admin_token),
    )
    assert update_response.status_code == 200
    delete_response = await client.delete(
        f"{API_PREFIX}/tasks/{task_id}", headers=auth(admin_token)
    )
    assert delete_response.status_code == 204
