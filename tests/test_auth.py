from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import create_access_token, verify_password
from app.models.user import User
from tests.conftest import API_PREFIX


async def test_registers_user_with_hashed_password(
    client: AsyncClient,
    session_factory,
) -> None:
    response = await client.post(
        f"{API_PREFIX}/users",
        json={
            "email": "new@example.com",
            "full_name": "New User",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert "password" not in body
    assert "hashed_password" not in body

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "new@example.com"))
        assert user is not None
        assert user.hashed_password != "StrongPassword123!"
        assert verify_password("StrongPassword123!", user.hashed_password)


async def test_duplicate_email_returns_409(
    client: AsyncClient,
    register_user,
) -> None:
    await register_user(email="duplicate@example.com")
    response = await client.post(
        f"{API_PREFIX}/users",
        json={
            "email": "duplicate@example.com",
            "full_name": "Duplicate",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 409


async def test_login_returns_bearer_token(
    client: AsyncClient,
    register_user,
) -> None:
    await register_user(email="login@example.com")
    response = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": "login@example.com", "password": "StrongPassword123!"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


async def test_login_rejects_wrong_password_and_unknown_user(
    client: AsyncClient,
    register_user,
) -> None:
    await register_user(email="known@example.com")

    for email, password in (
        ("known@example.com", "WrongPassword123!"),
        ("missing@example.com", "StrongPassword123!"),
    ):
        response = await client.post(
            f"{API_PREFIX}/auth/login",
            data={"username": email, "password": password},
        )
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


async def test_auth_me_returns_current_user(
    client: AsyncClient,
    register_user,
    login_user,
) -> None:
    user = await register_user(email="me@example.com")
    token = await login_user("me@example.com")
    response = await client.get(
        f"{API_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]
    assert response.json()["email"] == "me@example.com"
    assert "hashed_password" not in response.json()


async def test_auth_me_requires_valid_non_expired_token(
    client: AsyncClient,
) -> None:
    expired_token = create_access_token("1", expires_delta=timedelta(seconds=-1))

    for headers in (
        {},
        {"Authorization": "Bearer invalid.token.value"},
        {"Authorization": f"Bearer {expired_token}"},
    ):
        response = await client.get(f"{API_PREFIX}/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"


async def test_inactive_user_returns_403(
    client: AsyncClient,
    register_user,
    login_user,
    session_factory,
) -> None:
    user_data = await register_user(email="inactive@example.com")
    token = await login_user("inactive@example.com")

    async with session_factory() as session:
        user = await session.get(User, user_data["id"])
        assert user is not None
        user.is_active = False
        await session.commit()

    response = await client.get(
        f"{API_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
