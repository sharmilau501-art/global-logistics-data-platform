"""Phase 4 reconciliation tests; these require only pytest, not DuckDB."""
from copy import deepcopy
import pytest
from logistics.warehouse_checks import validate_warehouse_counts

LAKE = {
    'silver_unique_event_rows': 47,
    'gold_distinct_shipments': 10,
    'delivered_shipments': 8,
    'late_deliveries': 2,
}
COUNTS = {
    'staging_event_rows': 47,
    'fact_event_rows': 47,
    'staging_shipment_rows': 10,
    'fact_shipment_rows': 10,
    'delivered_shipments': 8,
    'late_deliveries': 2,
    'distinct_fact_shipments': 10,
    'distinct_fact_events': 47,
    'carrier_mart_shipments': 10,
    'route_mart_shipments': 10,
    'daily_mart_events': 47,
    'orphan_carrier_keys': 0,
    'orphan_route_keys': 0,
    'orphan_planned_date_keys': 0,
    'orphan_event_date_keys': 0,
}


def test_reconciled_counts_pass():
    validate_warehouse_counts(LAKE, COUNTS)


@pytest.mark.parametrize('name,broken_value', [
    ('fact_event_rows', 48),
    ('fact_shipment_rows', 9),
    ('late_deliveries', 3),
    ('distinct_fact_shipments', 9),
    ('carrier_mart_shipments', 11),
    ('route_mart_shipments', 9),
    ('daily_mart_events', 46),
    ('orphan_carrier_keys', 1),
    ('orphan_route_keys', 1),
    ('orphan_planned_date_keys', 1),
    ('orphan_event_date_keys', 1),
    ('fact_event_rows', -1),
] )
def test_reconciliation_failure_detected(name, broken_value):
    bad = deepcopy(COUNTS)
    bad[name] = broken_value
    with pytest.raises(ValueError):
        validate_warehouse_counts(LAKE, bad)


def test_bad_lake_metric_fails():
    bad = deepcopy(LAKE)
    bad['silver_unique_event_rows'] = -5
    with pytest.raises(ValueError):
        validate_warehouse_counts(bad, COUNTS)


def test_missing_count_fails():
    bad = deepcopy(COUNTS)
    del bad['staging_event_rows']
    with pytest.raises(ValueError):
        validate_warehouse_counts(LAKE, bad)
