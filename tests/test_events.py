import pytest
from fastapi.testclient import TestClient

from app.db import get_table
from app.main import app


class FakeTable:
    def __init__(self):
        self.records = {}

    def put_item(self, *, Item, ConditionExpression):
        assert ConditionExpression == (
            "attribute_not_exists(event_id)"
        )
        self.records[Item["event_id"]] = Item

    def get_item(self, *, Key, ConsistentRead):
        assert ConsistentRead is True
        event = self.records.get(Key["event_id"])
        return {"Item": event} if event else {}


@pytest.fixture
def client():
    fake_table = FakeTable()
    app.dependency_overrides[get_table] = lambda: fake_table

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_table, None)


def test_create_and_retrieve_event(client):
    response = client.post(
        "/events",
        json={
            "event_type": "outage",
            "message": "Service became unavailable",
        },
    )

    assert response.status_code == 201
    event = response.json()
    assert event["event_id"]
    assert event["created_at"]
    assert event["event_type"] == "outage"

    fetched = client.get(f"/events/{event['event_id']}")

    assert fetched.status_code == 200
    assert fetched.json() == event


def test_missing_event_returns_404(client):
    response = client.get("/events/does-not-exist")
    assert response.status_code == 404


def test_invalid_event_returns_422(client):
    response = client.post(
        "/events",
        json={"event_type": "", "message": ""},
    )
    assert response.status_code == 422
