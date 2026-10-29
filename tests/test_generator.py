from collections import Counter

import pytest

from logistics.generator import EVENT_TYPES, create_events, write_jsonl
from logistics.inspect import inspect_file


def test_deterministic_for_same_seed():
    assert create_events(shipments=7, seed=21) == create_events(shipments=7, seed=21)


def test_ids_types_and_realistic_duplicate_events():
    events = create_events(shipments=20, seed=42, duplicate_rate=0.1)
    ids = Counter(e["event_id"] for e in events)
    assert sum(n - 1 for n in ids.values()) > 0
    assert len({e["shipment_id"] for e in events}) == 20
    assert {e["event_type"] for e in events}.issubset(EVENT_TYPES)


def test_quality_inspector(tmp_path):
    events = create_events(shipments=10, seed=5, duplicate_rate=0.1)
    path = tmp_path / "events.jsonl"
    write_jsonl(events, path)
    result = inspect_file(path)
    assert result["invalid_rows"] == 0
    assert result["distinct_shipments"] == 10
    assert result["rows"] == len(events)
    assert result["duplicate_event_rows"] > 0


def test_invalid_configuration():
    with pytest.raises(ValueError):
        create_events(shipments=0)
    with pytest.raises(ValueError):
        create_events(duplicate_rate=2)


def test_shipment_attributes_do_not_change_across_events():
    events = create_events(shipments=20)
    attrs = {}
    for e in events:
        values = (e["carrier"], e["weight_kg"], e["origin_city"], e["destination_city"])
        attrs.setdefault(e["shipment_id"], values)
        assert attrs[e["shipment_id"]] == values
