from datetime import datetime, timezone
from uuid import uuid4

from botocore.exceptions import EndpointConnectionError
from fastapi.testclient import TestClient

from app.db import get_table
from app.main import app
from app.metrics import METRICS_REGISTRY


def metric_value(name, labels):
    value = METRICS_REGISTRY.get_sample_value(
        name, labels
    )
    return 0.0 if value is None else float(value)


def test_metrics_endpoint_exposes_prometheus_format():
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "text/plain"
    )

    body = response.text

    assert "# HELP http_requests_total" in body
    assert "# TYPE http_requests_total counter" in body
    assert "# HELP http_request_duration_seconds" in body
    assert "# TYPE http_request_duration_seconds histogram" in body


def test_http_request_counter_increments():
    labels = {
        "method": "GET",
        "route": "/health",
        "status_code": "200",
    }

    before = metric_value("http_requests_total", labels)

    with TestClient(app) as client:
        response = client.get("/health")

    after = metric_value("http_requests_total", labels)

    assert response.status_code == 200
    assert after == before + 1


def test_request_duration_histogram_observes_requests():
    labels = {
        "method": "GET",
        "route": "/health",
    }

    before = metric_value(
        "http_request_duration_seconds_count",
        labels,
    )

    with TestClient(app) as client:
        response = client.get("/health")

    after = metric_value(
        "http_request_duration_seconds_count",
        labels,
    )

    assert response.status_code == 200
    assert after == before + 1

    duration_sum = metric_value(
        "http_request_duration_seconds_sum",
        labels,
    )

    assert duration_sum > 0


def test_database_failure_increments_503_counter():
    class FailedTable:
        def get_item(self, **kwargs):
            raise EndpointConnectionError(
                endpoint_url="http://127.0.0.1:8000"
            )

    labels = {
        "method": "GET",
        "route": "/ready",
        "status_code": "503",
    }

    before = metric_value("http_requests_total", labels)

    app.dependency_overrides[get_table] = (
        lambda: FailedTable()
    )

    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_table, None)

    after = metric_value("http_requests_total", labels)

    assert response.status_code == 503
    assert after == before + 1
    assert len(response.headers["X-Request-ID"]) == 32


def test_metrics_use_route_templates_not_event_ids():
    event_id = str(uuid4())

    class ExistingTable:
        def get_item(self, **kwargs):
            return {
                "Item": {
                    "event_id": event_id,
                    "event_type": "metrics_test",
                    "message": "Verify safe metric labels",
                    "service": "cloud-reliability-platform",
                    "created_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }
            }

    labels = {
        "method": "GET",
        "route": "/events/{event_id}",
        "status_code": "200",
    }

    before = metric_value("http_requests_total", labels)

    app.dependency_overrides[get_table] = (
        lambda: ExistingTable()
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/events/{event_id}"
            )
            metrics_response = client.get("/metrics")
    finally:
        app.dependency_overrides.pop(get_table, None)

    after = metric_value("http_requests_total", labels)

    assert response.status_code == 200
    assert after == before + 1
    assert 'route="/events/{event_id}"' in (
        metrics_response.text
    )
    assert event_id not in metrics_response.text
    assert 'route="/metrics"' not in metrics_response.text
