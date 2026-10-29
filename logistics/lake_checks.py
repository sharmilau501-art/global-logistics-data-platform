"""No-dependency quality checks for Phase 3 Spark job metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_metrics(metrics: dict) -> None:
    required = ("input_rows", "valid_rows", "invalid_rows", "duplicate_event_rows",
                "silver_unique_event_rows", "gold_distinct_shipments",
                "delivered_shipments", "late_deliveries")
    for key in required:
        value = metrics.get(key)
        if type(value) is not int or value < 0:
            raise ValueError(f"{key} must be a nonnegative integer")
    if metrics["input_rows"] != metrics["valid_rows"] + metrics["invalid_rows"]:
        raise ValueError("source reconciliation failed: input != valid + invalid")
    if metrics["valid_rows"] != (metrics["silver_unique_event_rows"] +
                                 metrics["duplicate_event_rows"]):
        raise ValueError("silver reconciliation failed: valid != unique + duplicates")
    if metrics["gold_distinct_shipments"] > metrics["silver_unique_event_rows"]:
        raise ValueError("more shipments than unique events")
    if metrics["delivered_shipments"] > metrics["gold_distinct_shipments"]:
        raise ValueError("more delivered shipments than shipments")
    if metrics["late_deliveries"] > metrics["delivered_shipments"]:
        raise ValueError("more late deliveries than delivered shipments")


def main():
    parser = argparse.ArgumentParser(description="Check Phase 3 data lake reconciliation metrics")
    parser.add_argument("--metrics", type=Path, default=Path("data/lake/quality_metrics.json"))
    args = parser.parse_args()
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    validate_metrics(metrics)
    print("PASS: input, silver, and gold reconciliation invariants")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
