"""Generate deterministic synthetic shipment events. No cloud calls, no credentials."""
from __future__ import annotations

import argparse
import json
import random
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOCATIONS = [
    ("Shanghai", "China", "Los Angeles", "United States"),
    ("Mumbai", "India", "New York", "United States"),
    ("Hamburg", "Germany", "Seattle", "United States"),
    ("Busan", "South Korea", "Oakland", "United States"),
    ("Singapore", "Singapore", "Houston", "United States"),
]
EVENT_TYPES = (
    "CREATED",
    "DEPARTED_ORIGIN",
    "ARRIVED_DESTINATION_PORT",
    "CUSTOMS_HOLD",
    "CUSTOMS_CLEARED",
    "RECEIVED_WAREHOUSE",
    "DELIVERED",
)
BASE_TIME = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)


def create_events(shipments: int = 200, seed: int = 42, duplicate_rate: float = 0.02) -> list[dict]:
    if shipments < 1:
        raise ValueError("shipments must be >= 1")
    if not 0 <= duplicate_rate <= 1:
        raise ValueError("duplicate_rate must be between 0 and 1")
    rng = random.Random(seed)
    events: list[dict] = []
    for index in range(shipments):
        shipment_id = f"SHIP-{index + 1:06d}"
        origin, origin_country, destination, destination_country = rng.choice(LOCATIONS)
        created_at = BASE_TIME + timedelta(hours=rng.randint(0, 24 * 7))
        carrier = rng.choice(["CARRIER_A", "CARRIER_B", "CARRIER_C"])
        weight_kg = round(rng.uniform(20, 1200), 2)
        customs_hold = rng.random() < 0.17
        delayed = rng.random() < 0.23
        delay_reason = rng.choice(["PORT_CONGESTION", "WEATHER", "CUSTOMS", "CARRIER_DELAY"]) if delayed else None
        steps = [
            ("CREATED", 0),
            ("DEPARTED_ORIGIN", 12),
            ("ARRIVED_DESTINATION_PORT", 72),
        ]
        if customs_hold:
            steps.append(("CUSTOMS_HOLD", 77))
        steps.extend([
            ("CUSTOMS_CLEARED", 92 if customs_hold else 78),
            ("RECEIVED_WAREHOUSE", 108 if customs_hold else 93),
            ("DELIVERED", 144 if customs_hold else 120),
        ])
        offset = 36 if delayed else 0
        planned_delivery = created_at + timedelta(hours=132)
        for sequence, (kind, hours) in enumerate(steps):
            event_at = created_at + timedelta(hours=hours + (offset if sequence >= 2 else 0))
            event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"logistics:{seed}:{shipment_id}:{sequence}:{kind}"))
            events.append({
                "event_id": event_id,
                "shipment_id": shipment_id,
                "event_type": kind,
                "event_timestamp": event_at.isoformat(),
                "ingested_timestamp": (event_at + timedelta(minutes=rng.randint(1, 90))).isoformat(),
                "origin_city": origin,
                "origin_country": origin_country,
                "destination_city": destination,
                "destination_country": destination_country,
                "carrier": carrier,
                "planned_delivery_timestamp": planned_delivery.isoformat(),
                "delay_reason": delay_reason if kind in ("ARRIVED_DESTINATION_PORT", "DELIVERED") else None,
                "weight_kg": weight_kg,
                "source_system": "synthetic_shipment_simulator",
            })
    # Deliberate replay duplicates allow realistic idempotency/dedup tests later.
    duplicate_count = round(len(events) * duplicate_rate)
    if duplicate_count:
        events.extend(dict(e) for e in rng.sample(events, duplicate_count))
    # Arrival order differs from event-time order, like a real stream.
    rng.shuffle(events)
    return events


def write_jsonl(events: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic logistics events, entirely offline.")
    parser.add_argument("--shipments", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--duplicate-rate", type=float, default=0.02)
    parser.add_argument("--output", type=Path, default=Path("data/raw/shipment_events.jsonl"))
    args = parser.parse_args()
    events = create_events(args.shipments, args.seed, args.duplicate_rate)
    write_jsonl(events, args.output)
    ids = Counter(e["event_id"] for e in events)
    duplicate_rows = sum(count - 1 for count in ids.values())
    print(f"Saved {len(events):,} event rows for {args.shipments:,} shipments to {args.output}")
    print(f"Unique event IDs: {len(ids):,} | Replay duplicate rows: {duplicate_rows:,}")
    print("Cloud services used: NONE | AWS charges: $0")


if __name__ == "__main__":
    main()
