"""Independent row-count and dimensional-integrity checks for local DuckDB warehouse.

This module deliberately has no DuckDB dependency so it can be unit-tested offline.
"""
from __future__ import annotations


def validate_warehouse_counts(lake: dict, warehouse: dict) -> None:
    """Raise ValueError if a local warehouse disagrees with Phase 3 lake metrics."""
    checks = {
        "staging_event_rows": "silver_unique_event_rows",
        "fact_event_rows": "silver_unique_event_rows",
        "staging_shipment_rows": "gold_distinct_shipments",
        "fact_shipment_rows": "gold_distinct_shipments",
        "delivered_shipments": "delivered_shipments",
        "late_deliveries": "late_deliveries",
    }
    for observed, expected in checks.items():
        actual_value = warehouse.get(observed)
        expected_value = lake.get(expected)
        if type(actual_value) is not int or actual_value < 0:
            raise ValueError(f"{observed} must be a nonnegative integer")
        if type(expected_value) is not int or expected_value < 0:
            raise ValueError(f"lake metric {expected} must be a nonnegative integer")
        if actual_value != expected_value:
            raise ValueError(
                f"{observed} mismatch: warehouse={actual_value} vs lake {expected}={expected_value}"
            )

    expected_shipments = lake["gold_distinct_shipments"]
    expected_events = lake["silver_unique_event_rows"]
    for field, expected in (
        ("distinct_fact_shipments", expected_shipments),
        ("distinct_fact_events", expected_events),
        ("carrier_mart_shipments", expected_shipments),
        ("route_mart_shipments", expected_shipments),
        ("daily_mart_events", expected_events),
    ):
        if type(warehouse.get(field)) is not int or warehouse[field] != expected:
            raise ValueError(f"{field} mismatch: expected {expected}, got {warehouse.get(field)}")

    for field in (
        "orphan_carrier_keys", "orphan_route_keys", "orphan_planned_date_keys", "orphan_event_date_keys"
    ):
        if warehouse.get(field) != 0 or type(warehouse[field]) is not int:
            raise ValueError(f"{field} must be 0, got {warehouse.get(field)}")
