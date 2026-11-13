from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "cloud-reliability-platform",
    }


def test_unknown_endpoint():
    response = client.get("/nonexistent")

    assert response.status_code == 404
