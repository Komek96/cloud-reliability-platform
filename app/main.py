import time

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

        app_logger.info(
            "HTTP request completed",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "method": request.method,
                "route": getattr(
                    route, "path", "unmatched"
                ),
                "status_code": status_code,
                "duration_ms": round(
                    (time.perf_counter() - started) * 1000,
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

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import get_table
from app.observability import app_logger


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
