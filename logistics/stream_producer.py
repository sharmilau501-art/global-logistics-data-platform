"""Send previously generated JSONL shipment events to a LOCAL Kafka broker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish synthetic shipments to LOCAL Kafka")
    parser.add_argument("--input", type=Path, default=Path("data/raw/shipment_events.jsonl"))
    parser.add_argument("--topic", default="shipment-events")
    parser.add_argument("--bootstrap", default="localhost:9092")
    parser.add_argument("--limit", type=int, default=0, help="0 = publish all records")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be >= 0")
    if not args.input.is_file():
        parser.error(f"Input file not found: {args.input}. Run Phase 1 generator first.")

    from kafka import KafkaProducer

    producer = KafkaProducer(bootstrap_servers=args.bootstrap,
                             acks="all", retries=3,
                             max_in_flight_requests_per_connection=1)
    acknowledgments = []
    published = 0
    try:
        with args.input.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                # All events for one shipment hash to the same Kafka partition.
                key = str(record["shipment_id"]).encode("utf-8")
                value = json.dumps(record, sort_keys=True).encode("utf-8")
                acknowledgments.append(producer.send(args.topic, key=key, value=value))
                published += 1
                if args.limit and published >= args.limit:
                    break
        # Verify broker acknowledgements, not just local send queueing.
        for acknowledgment in acknowledgments:
            acknowledgment.get(timeout=30)
        producer.flush(timeout=30)
    finally:
        producer.close()
    print(f"Published and acknowledged {published:,} rows to {args.topic} at {args.bootstrap}")
    print("Source: generated local synthetic data | AWS charges: $0")


if __name__ == "__main__":
    main()
