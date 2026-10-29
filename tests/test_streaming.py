"""Phase 2 validation is testable without Docker or a running broker."""
import json

from logistics.generator import create_events
from logistics.streaming import classify_record, validate_shipment_event


def test_generated_records_are_valid():
    for event in create_events(shipments=8, seed=42):
        assert validate_shipment_event(event)


def test_replay_duplicate_is_not_accepted_twice():
    event = create_events(shipments=1, seed=42)[0]
    seen = set()
    assert classify_record(json.dumps(event).encode(), seen)[0] == "accepted"
    assert classify_record(json.dumps(event).encode(), seen)[0] == "duplicate"
    assert len(seen) == 1


def test_invalid_json_and_incomplete_event_are_rejected():
    assert classify_record(b"{not-json", set())[0] == "invalid"
    assert classify_record(b'{"event_id":"x"}', set())[0] == "invalid"


def test_replay_data_keeps_unique_event_ids():
    events = create_events(shipments=30, seed=99, duplicate_rate=0.15)
    seen = set()
    statuses = [classify_record(json.dumps(e).encode(), seen)[0] for e in events]
    assert statuses.count("duplicate") > 0
    assert statuses.count("accepted") == len({e["event_id"] for e in events})
    assert statuses.count("invalid") == 0
