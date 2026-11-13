from fastapi import FastAPI

app = FastAPI(
    title="Cloud Reliability Platform",
    version="0.1.0",
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
