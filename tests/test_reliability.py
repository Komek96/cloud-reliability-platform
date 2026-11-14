import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi.testclient import TestClient

from app.db import get_table
from app.main import app


class UnavailableTable:
    def put_item(self, **kwargs):
        raise EndpointConnectionError(
            endpoint_url="http://dynamodb:8000"
        )

    def get_item(self, **kwargs):
        raise ClientError(
            {
                "Error": {
                    "Code": "ProvisionedThroughputExceededException",
                    "Message": "Internal database details",
                }
            },
            "GetItem",
        )


@pytest.fixture
def unavailable_client():
    app.dependency_overrides[get_table] = lambda: UnavailableTable()

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_table, None)


def test_database_outage_during_event_creation(unavailable_client):
    response = unavailable_client.post(
        "/events",
        json={
            "event_type": "outage",
            "message": "Simulated database failure",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Event storage temporarily unavailable"
    }
    assert "dynamodb:8000" not in response.text


def test_database_service_error_during_event_lookup(unavailable_client):
    response = unavailable_client.get("/events/test-event-id")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Event storage temporarily unavailable"
    }
    assert "Internal database details" not in response.text


def test_health_endpoint_survives_database_outage(unavailable_client):
    response = unavailable_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
