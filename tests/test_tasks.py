from httpx import AsyncClient

from tests.conftest import API_PREFIX


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_user_can_complete_own_task_crud(
    client: AsyncClient,
    register_user,
    login_user,
) -> None:
    user = await register_user(email="owner@example.com")
    token = await login_user("owner@example.com")

    create_response = await client.post(
        f"{API_PREFIX}/tasks",
        json={"title": "First task", "description": "Details"},
        headers=auth(token),
    )
    assert create_response.status_code == 201
    task = create_response.json()
    assert task["owner_id"] == user["id"]
    assert task["completed"] is False

    list_response = await client.get(f"{API_PREFIX}/tasks", headers=auth(token))
    assert list_response.status_code == 200
    assert list_response.json()["items"] == [task]
    assert list_response.json()["total"] == 1

    get_response = await client.get(
        f"{API_PREFIX}/tasks/{task['id']}",
        headers=auth(token),
    )
    assert get_response.status_code == 200

    patch_response = await client.patch(
        f"{API_PREFIX}/tasks/{task['id']}",
        json={"completed": True},
        headers=auth(token),
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "First task"
    assert patch_response.json()["completed"] is True

    delete_response = await client.delete(
        f"{API_PREFIX}/tasks/{task['id']}",
        headers=auth(token),
    )
    assert delete_response.status_code == 204
    assert delete_response.content == b""


async def test_client_cannot_choose_or_change_owner(
    client: AsyncClient,
    register_user,
    login_user,
) -> None:
    await register_user(email="fixed-owner@example.com")
    token = await login_user("fixed-owner@example.com")

    create_response = await client.post(
        f"{API_PREFIX}/tasks",
        json={"title": "Task", "owner_id": 999},
        headers=auth(token),
    )
    assert create_response.status_code == 422

    valid_response = await client.post(
        f"{API_PREFIX}/tasks",
        json={"title": "Task"},
        headers=auth(token),
    )
    task_id = valid_response.json()["id"]
    patch_response = await client.patch(
        f"{API_PREFIX}/tasks/{task_id}",
        json={"owner_id": 999},
        headers=auth(token),
    )
    assert patch_response.status_code == 422

    null_response = await client.patch(
        f"{API_PREFIX}/tasks/{task_id}",
        json={"completed": None},
        headers=auth(token),
    )
    assert null_response.status_code == 422


async def test_missing_task_returns_404(
    client: AsyncClient,
    register_user,
    login_user,
) -> None:
    await register_user(email="missing-task@example.com")
    token = await login_user("missing-task@example.com")

    for method in ("get", "patch", "delete"):
        request = getattr(client, method)
        kwargs = {"json": {"title": "Updated"}} if method == "patch" else {}
        response = await request(
            f"{API_PREFIX}/tasks/999",
            headers=auth(token),
            **kwargs,
        )
        assert response.status_code == 404


async def test_user_cannot_access_another_users_task(
    client: AsyncClient,
    register_user,
    login_user,
) -> None:
    await register_user(email="user-a@example.com")
    token_a = await login_user("user-a@example.com")
    await register_user(email="user-b@example.com")
    token_b = await login_user("user-b@example.com")

    task_response = await client.post(
        f"{API_PREFIX}/tasks",
        json={"title": "Private"},
        headers=auth(token_a),
    )
    task_id = task_response.json()["id"]

    requests = (
        client.get(f"{API_PREFIX}/tasks/{task_id}", headers=auth(token_b)),
        client.patch(
            f"{API_PREFIX}/tasks/{task_id}",
            json={"title": "Stolen"},
            headers=auth(token_b),
        ),
        client.delete(f"{API_PREFIX}/tasks/{task_id}", headers=auth(token_b)),
    )
    for request in requests:
        response = await request
        assert response.status_code == 403

    list_response = await client.get(f"{API_PREFIX}/tasks", headers=auth(token_b))
    assert list_response.json()["items"] == []
