from httpx import AsyncClient

from tests.conftest import API_PREFIX
from tests.test_tasks import auth


async def test_regular_user_cannot_access_admin_endpoints(
    client: AsyncClient,
    register_user,
    login_user,
) -> None:
    user = await register_user(email="regular@example.com")
    token = await login_user("regular@example.com")
    other_user = await register_user(email="other@example.com")

    list_response = await client.get(f"{API_PREFIX}/users", headers=auth(token))
    admin_patch_response = await client.patch(
        f"{API_PREFIX}/users/{user['id']}/admin",
        json={"role": "admin"},
        headers=auth(token),
    )
    cross_user_response = await client.patch(
        f"{API_PREFIX}/users/{other_user['id']}",
        json={"full_name": "Changed by stranger"},
        headers=auth(token),
    )

    assert list_response.status_code == 403
    assert admin_patch_response.status_code == 403
    assert cross_user_response.status_code == 403


async def test_admin_can_change_user_role_and_status(
    client: AsyncClient,
    register_user,
    make_admin,
    login_user,
) -> None:
    user = await register_user(email="promoted@example.com")
    await make_admin()
    admin_token = await login_user("admin@example.com", "AdminPassword123!")
    response = await client.patch(
        f"{API_PREFIX}/users/{user['id']}/admin",
        json={"role": "admin", "is_active": False},
        headers=auth(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert response.json()["is_active"] is False


async def test_registration_cannot_self_assign_admin(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"{API_PREFIX}/users",
        json={
            "email": "self-admin@example.com",
            "full_name": "Self Admin",
            "password": "StrongPassword123!",
            "role": "admin",
        },
    )
    assert response.status_code == 422


async def test_admin_can_list_users_without_password_hashes(
    client: AsyncClient,
    register_user,
    make_admin,
    login_user,
) -> None:
    await register_user(email="listed@example.com")
    await make_admin()
    token = await login_user("admin@example.com", "AdminPassword123!")
    response = await client.get(f"{API_PREFIX}/users", headers=auth(token))

    assert response.status_code == 200
    assert response.json()["total"] == 2
    for user in response.json()["items"]:
        assert "password" not in user
        assert "hashed_password" not in user


async def test_admin_can_manage_any_users_tasks(
    client: AsyncClient,
    register_user,
    make_admin,
    login_user,
) -> None:
    await register_user(email="task-owner@example.com")
    owner_token = await login_user("task-owner@example.com")
    task_response = await client.post(
        f"{API_PREFIX}/tasks",
        json={"title": "Owner task"},
        headers=auth(owner_token),
    )
    task_id = task_response.json()["id"]

    await make_admin()
    admin_token = await login_user("admin@example.com", "AdminPassword123!")

    list_response = await client.get(
        f"{API_PREFIX}/tasks",
        headers=auth(admin_token),
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = await client.get(
        f"{API_PREFIX}/tasks/{task_id}",
        headers=auth(admin_token),
    )
    assert get_response.status_code == 200

    patch_response = await client.patch(
        f"{API_PREFIX}/tasks/{task_id}",
        json={"title": "Admin updated"},
        headers=auth(admin_token),
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["title"] == "Admin updated"

    delete_response = await client.delete(
        f"{API_PREFIX}/tasks/{task_id}",
        headers=auth(admin_token),
    )
    assert delete_response.status_code == 204
