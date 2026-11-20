import time
from datetime import datetime, timezone
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.db import get_table
from app.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    METRICS_REGISTRY,
)
from app.observability import app_logger

app = FastAPI(
    title="Cloud Reliability Platform",
    version="0.1.0",
)


@app.middleware("http")
async def log_http_request(request: Request, call_next):
    """Record HTTP responses with correlation IDs."""
    request_id = uuid4().hex
    request.state.request_id = request_id

    started = time.perf_counter()
    status_code = 500

    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        elapsed_seconds = time.perf_counter() - started

        if route_path != "/metrics":
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                route=route_path,
                status_code=str(status_code),
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                route=route_path,
            ).observe(elapsed_seconds)

        app_logger.info(
            "HTTP request completed",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": route_path,
                "status_code": status_code,
                "duration_ms": round(
                    elapsed_seconds * 1000,
                    2,
                ),
            },
        )


@app.exception_handler(BotoCoreError)
@app.exception_handler(ClientError)
async def handle_database_failure(request: Request, exc: Exception):
    """Return a safe response when DynamoDB operations fail."""
    app_logger.error(
        "Database dependency failure",
        extra={
            "event": "database_failure",
            "request_id": getattr(
                request.state, "request_id", None
            ),
            "method": request.method,
            "route": getattr(
                request.scope.get("route"),
                "path",
                "unmatched",
            ),
            "status_code": 503,
            "error_type": type(exc).__name__,
        },
    )

    return JSONResponse(
        status_code=503,
        content={"detail": "Event storage temporarily unavailable"},
    )


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "cloud-reliability-platform",
    }

@app.get("/metrics", include_in_schema=False)
def prometheus_metrics():
    """Expose HTTP metrics for Prometheus scraping."""
    return Response(
        content=generate_latest(METRICS_REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=500)
    service: str = Field(
        default="cloud-reliability-platform",
        min_length=1,
        max_length=128,
    )


class EventRecord(EventCreate):
    event_id: str
    created_at: str


@app.post("/events", status_code=201, response_model=EventRecord)
def create_event(payload: EventCreate, table=Depends(get_table)):
    event = EventRecord(
        **payload.model_dump(),
        event_id=str(uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    table.put_item(
        Item=event.model_dump(),
        ConditionExpression="attribute_not_exists(event_id)",
    )

    return event


@app.get("/events/{event_id}", response_model=EventRecord)
def get_event(event_id: str, table=Depends(get_table)):
    result = table.get_item(
        Key={"event_id": event_id},
        ConsistentRead=True,
    )

    if "Item" not in result:
        raise HTTPException(
            status_code=404,
            detail="Event not found",
        )

    return EventRecord.model_validate(result["Item"])

@app.get("/ready")
def readiness_check(table=Depends(get_table)):
    """Verify that DynamoDB can serve event reads."""
    table.get_item(
        Key={"event_id": "__readiness_probe__"},
        ConsistentRead=True,
    )

    return {
        "status": "ready",
        "service": "cloud-reliability-platform",
    }
