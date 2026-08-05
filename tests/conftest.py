from collections.abc import AsyncIterator, Awaitable, Callable

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db_session
from app.main import app
from app.models.user import User, UserRole

API_PREFIX = "/api/v1"


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    database_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncIterator[AsyncClient]:
    async def override_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db_session] = override_db_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def register_user(client: AsyncClient) -> Callable[..., Awaitable[dict]]:
    counter = 0

    async def register(
        email: str | None = None,
        password: str = "StrongPassword123!",
        full_name: str = "Test User",
    ) -> dict:
        nonlocal counter
        counter += 1
        response = await client.post(
            f"{API_PREFIX}/users",
            json={
                "email": email or f"user{counter}@example.com",
                "full_name": full_name,
                "password": password,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return register


@pytest_asyncio.fixture
async def login_user(client: AsyncClient) -> Callable[..., Awaitable[str]]:
    async def login(email: str, password: str = "StrongPassword123!") -> str:
        response = await client.post(
            f"{API_PREFIX}/auth/login",
            data={"username": email, "password": password},
        )
        assert response.status_code == 200, response.text
        return response.json()["access_token"]

    return login


@pytest_asyncio.fixture
async def make_admin(session_factory) -> Callable[..., Awaitable[User]]:
    async def create(
        email: str = "admin@example.com",
        password: str = "AdminPassword123!",
    ) -> User:
        async with session_factory() as session:
            user = User(
                email=email,
                full_name="Administrator",
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return create
