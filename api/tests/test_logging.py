from collections.abc import Iterator

import pytest
import structlog
from fakeredis import FakeAsyncRedis
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from finance_api.dependencies import get_redis
from finance_api.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_redis] = lambda: FakeAsyncRedis()
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_each_request_is_logged_with_a_request_id(client: TestClient) -> None:
    # capture_logs() disables the configured processors; re-add the one that merges in
    # request-scoped fields like request_id.
    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs:
        response = client.get("/health")

    request_id = response.headers["X-Request-ID"]
    [entry] = [log for log in logs if log["event"] == "request"]
    assert entry["status"] == 200
    assert entry["request_id"] == request_id
    assert entry["path"] == "/health"
    assert entry["latency_ms"] >= 0


def test_incoming_request_id_is_reused(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-123"})

    assert response.headers["X-Request-ID"] == "trace-123"
