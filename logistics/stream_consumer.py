"""Read locally streamed events; validate and remove replay duplicates."""
from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from .streaming import classify_record


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume and validate local Kafka shipment events")
    parser.add_argument("--topic", default="shipment-events")
    parser.add_argument("--bootstrap", default="localhost:9092")
    parser.add_argument("--output", type=Path, default=Path("data/stream/unique_shipment_events.jsonl"))
    parser.add_argument("--rejected", type=Path, default=Path("data/stream/rejected_events.jsonl"))
    parser.add_argument("--metrics", type=Path, default=Path("data/stream/consumer_metrics.json"))
    parser.add_argument("--idle-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if args.idle_seconds <= 0:
        parser.error("--idle-seconds must be positive")

    from kafka import KafkaConsumer

    # Unique group for each invocation: easy, repeatable local replays from earliest.
    consumer = KafkaConsumer(args.topic, bootstrap_servers=args.bootstrap,
                             group_id=f"shipment-phase2-{uuid.uuid4().hex[:12]}",
                             auto_offset_reset="earliest", enable_auto_commit=False)
    for path in (args.output, args.rejected, args.metrics):
        path.parent.mkdir(parents=True, exist_ok=True)

    metrics = {"received": 0, "accepted": 0, "duplicates": 0, "invalid": 0,
               "distinct_shipments": 0}
    seen_ids: set[str] = set()
    shipment_ids: set[str] = set()
    last_received = time.monotonic()
    try:
        with args.output.open("w", encoding="utf-8") as accepted, args.rejected.open("w", encoding="utf-8") as rejected:
            while time.monotonic() - last_received < args.idle_seconds:
                batches = consumer.poll(timeout_ms=1000)
                for records in batches.values():
                    for message in records:
                        last_received = time.monotonic()
                        metrics["received"] += 1
                        status, event = classify_record(message.value, seen_ids)
                        if status == "accepted":
                            metrics["accepted"] += 1
                            shipment_ids.add(event["shipment_id"])
                            accepted.write(json.dumps(event, sort_keys=True) + "\n")
                        elif status == "duplicate":
                            metrics["duplicates"] += 1
                        else:
                            metrics["invalid"] += 1
                            rejected.write(message.value.decode("utf-8", errors="replace") + "\n")
        metrics["distinct_shipments"] = len(shipment_ids)
        args.metrics.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    finally:
        consumer.close()
    print(json.dumps(metrics, indent=2))
    print(f"Unique events: {args.output}")
    print(f"Consumer metrics: {args.metrics}")
    print("Local Kafka only | AWS charges: $0")


if __name__ == "__main__":
    main()
