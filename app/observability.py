"""Structured operational logging for the API."""

import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Serialize operational log records as JSON."""

    FIELDS = (
        "request_id",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "error_type",
    )

    def format(self, record):
        entry = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "level": record.levelname,
            "event": getattr(
                record, "event", "application_log"
            ),
            "message": record.getMessage(),
        }

        for field in self.FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)

        return json.dumps(entry, ensure_ascii=False)


app_logger = logging.getLogger(
    "cloud_reliability_platform"
)

app_logger.setLevel(logging.INFO)
app_logger.propagate = False

if not app_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    app_logger.addHandler(handler)
