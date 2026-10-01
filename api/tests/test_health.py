from fastapi.testclient import TestClient

from finance_api.main import app


def test_health_returns_ok() -> None:
    # Using TestClient as a context manager runs the app's startup/shutdown (lifespan).
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
