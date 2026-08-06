from httpx import AsyncClient

from tests.conftest import API_PREFIX


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "message": "FastAPI application is running",
    }
