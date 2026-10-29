"""Inspect synthetic JSONL events and calculate quality metrics."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .generator import EVENT_TYPES

REQUIRED = {"event_id", "shipment_id", "event_type", "event_timestamp", "ingested_timestamp", "origin_city", "destination_city", "planned_delivery_timestamp", "source_system"}


def inspect_file(path: Path) -> dict:
    total = 0
    invalid = 0
    ids: Counter[str] = Counter()
    shipments: set[str] = set()
    kinds: Counter[str] = Counter()
    with path.open("r", encoding="utf-8") as handle:
        for row in handle:
            if not row.strip():
                continue
            total += 1
            try:
                record = json.loads(row)
                if not REQUIRED.issubset(record) or record["event_type"] not in EVENT_TYPES:
                    raise ValueError("Missing required fields or invalid event type")
                datetime.fromisoformat(record["event_timestamp"])
                datetime.fromisoformat(record["ingested_timestamp"])
            except (ValueError, TypeError, json.JSONDecodeError):
                invalid += 1
                continue
            ids[record["event_id"]] += 1
            shipments.add(record["shipment_id"])
            kinds[record["event_type"]] += 1
    return {
        "rows": total,
        "valid_rows": total - invalid,
        "invalid_rows": invalid,
        "distinct_shipments": len(shipments),
        "unique_event_ids": len(ids),
        "duplicate_event_rows": sum(n - 1 for n in ids.values()),
        "event_types": dict(sorted(kinds.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check local event quality.")
    parser.add_argument("--input", type=Path, default=Path("data/raw/shipment_events.jsonl"))
    args = parser.parse_args()
    print(json.dumps(inspect_file(args.input), indent=2))


if __name__ == "__main__":
    main()
