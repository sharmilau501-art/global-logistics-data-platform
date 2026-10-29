"""Portable tests that do not need Docker, Java or PySpark."""
from copy import deepcopy

import pytest

from logistics.lake_checks import validate_metrics


METRICS = {
    "input_rows": 52, "valid_rows": 50, "invalid_rows": 2,
    "duplicate_event_rows": 5, "silver_unique_event_rows": 45,
    "gold_distinct_shipments": 10, "delivered_shipments": 6, "late_deliveries": 2,
}


def test_valid_metrics():
    validate_metrics(METRICS)


@pytest.mark.parametrize("field,value", [
    ("input_rows", 53),
    ("duplicate_event_rows", 6),
    ("gold_distinct_shipments", 46),
    ("delivered_shipments", 11),
    ("late_deliveries", 7),
    ("invalid_rows", -1),
    ("valid_rows", 50.0),
])
def test_invalid_metrics(field, value):
    bad = deepcopy(METRICS)
    bad[field] = value
    with pytest.raises(ValueError):
        validate_metrics(bad)
