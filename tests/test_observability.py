import json
import logging

from botocore.exceptions import EndpointConnectionError
from fastapi.testclient import TestClient

from app.db import get_table
from app.main import app
from app.observability import JSONFormatter, app_logger


class CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_json_formatter():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP request completed",
        args=(),
        exc_info=None,
    )
    record.event = "http_request"
    record.status_code = 200

    entry = json.loads(JSONFormatter().format(record))

    assert entry["level"] == "INFO"
    assert entry["event"] == "http_request"
    assert entry["status_code"] == 200
    assert "timestamp" in entry


def test_request_logging_and_correlation_id():
    capture = CaptureHandler()
    app_logger.addHandler(capture)

    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        app_logger.removeHandler(capture)

    assert response.status_code == 200

    request_id = response.headers["X-Request-ID"]
    assert len(request_id) == 32

    entries = [
        json.loads(JSONFormatter().format(record))
        for record in capture.records
    ]

    requests = [
        entry for entry in entries
        if entry["event"] == "http_request"
    ]

    assert len(requests) == 1
    assert requests[0]["method"] == "GET"
    assert requests[0]["route"] == "/health"
    assert requests[0]["status_code"] == 200
    assert requests[0]["request_id"] == request_id
    assert requests[0]["duration_ms"] >= 0


def test_database_failure_produces_structured_log():
    class FailedTable:
        def get_item(self, **kwargs):
            raise EndpointConnectionError(
                endpoint_url="http://dynamodb:8000"
            )

    capture = CaptureHandler()
    app_logger.addHandler(capture)

    app.dependency_overrides[get_table] = (
        lambda: FailedTable()
    )

    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_table, None)
        app_logger.removeHandler(capture)

    assert response.status_code == 503

    entries = [
        json.loads(JSONFormatter().format(record))
        for record in capture.records
    ]

    failures = [
        entry for entry in entries
        if entry["event"] == "database_failure"
    ]

    requests = [
        entry for entry in entries
        if entry["event"] == "http_request"
    ]

    assert len(failures) == 1
    assert len(requests) == 1

    assert failures[0]["error_type"] == (
        "EndpointConnectionError"
    )
    assert failures[0]["status_code"] == 503
    assert requests[0]["status_code"] == 503

    request_id = response.headers["X-Request-ID"]

    assert failures[0]["request_id"] == request_id
    assert requests[0]["request_id"] == request_id

    assert "dynamodb:8000" not in json.dumps(entries)
