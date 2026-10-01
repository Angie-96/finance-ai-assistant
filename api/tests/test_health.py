from collections.abc import Iterator

import pytest
from fakeredis import FakeAsyncRedis
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from finance_api.dependencies import get_redis
from finance_api.main import app


class DownRedis(FakeAsyncRedis):
    """A Redis client whose server is unreachable."""

    async def ping(self, **kwargs: object) -> bool:
        raise RedisConnectionError("Connection refused")


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Using TestClient as a context manager runs the app's startup/shutdown (lifespan).
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_health_ok_when_redis_responds(client: TestClient) -> None:
    app.dependency_overrides[get_redis] = lambda: FakeAsyncRedis()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "redis": "ok"}


def test_health_503_when_redis_is_down(client: TestClient) -> None:
    app.dependency_overrides[get_redis] = lambda: DownRedis()

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "redis": "unavailable"}
