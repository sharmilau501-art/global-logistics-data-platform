"""Kafka-agnostic stream validation and idempotent event-ID deduplication."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .generator import EVENT_TYPES
from .inspect import REQUIRED


def validate_shipment_event(event: Any) -> bool:
    if not isinstance(event, dict) or not REQUIRED.issubset(event):
        return False
    for name in ("event_id", "shipment_id", "event_type", "source_system"):
        if not isinstance(event.get(name), str) or not event[name].strip():
            return False
    if event["event_type"] not in EVENT_TYPES:
        return False
    for name in ("event_timestamp", "ingested_timestamp", "planned_delivery_timestamp"):
        timestamp = event.get(name)
        if not isinstance(timestamp, str):
            return False
        try:
            datetime.fromisoformat(timestamp)
        except ValueError:
            return False
    return True


def classify_record(raw: bytes | str, seen_ids: set[str]) -> tuple[str, dict | None]:
    """Returns ('accepted'|'duplicate'|'invalid', event or None)."""
    try:
        event = json.loads(raw)
    except (ValueError, TypeError, UnicodeDecodeError):
        return "invalid", None
    if not validate_shipment_event(event):
        return "invalid", event if isinstance(event, dict) else None
    event_id = event["event_id"]
    if event_id in seen_ids:
        return "duplicate", event
    seen_ids.add(event_id)
    return "accepted", event
