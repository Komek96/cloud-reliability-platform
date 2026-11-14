import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi.testclient import TestClient

from app.db import get_table
from app.main import app


class AvailableTable:
    def get_item(self, *, Key, ConsistentRead):
        assert Key == {"event_id": "__readiness_probe__"}
        assert ConsistentRead is True
        return {}


class UnavailableTable:
    def __init__(self, error):
        self.error = error

    def get_item(self, **kwargs):
        raise self.error


@pytest.fixture
def client_for_table():
    def create_client(table):
        app.dependency_overrides[get_table] = lambda: table
        return TestClient(app)

    try:
        yield create_client
    finally:
        app.dependency_overrides.pop(get_table, None)


def test_ready_when_database_available(client_for_table):
    with client_for_table(AvailableTable()) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "cloud-reliability-platform",
    }


@pytest.mark.parametrize(
    "error",
    [
        EndpointConnectionError(
            endpoint_url="http://dynamodb:8000"
        ),
        ClientError(
            {
                "Error": {
                    "Code": "InternalServerError",
                    "Message": "Private database details",
                }
            },
            "GetItem",
        ),
    ],
)
def test_not_ready_when_database_fails(
    client_for_table, error
):
    with client_for_table(UnavailableTable(error)) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Event storage temporarily unavailable"
    }

    assert "Private database details" not in response.text
    assert "dynamodb:8000" not in response.text


def test_liveness_independent_of_readiness(client_for_table):
    error = EndpointConnectionError(
        endpoint_url="http://dynamodb:8000"
    )

    with client_for_table(UnavailableTable(error)) as client:
        health = client.get("/health")
        readiness = client.get("/ready")

    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    assert readiness.status_code == 503
