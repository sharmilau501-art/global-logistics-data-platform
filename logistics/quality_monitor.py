"""Offline Phase 5 quality gate for the local Global Logistics platform.

Reads existing Phase 3/4 metrics and LIVE DuckDB fact/mart row counts.
No network, AWS, emails, or paid services.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .lake_checks import validate_metrics
from .warehouse_checks import validate_warehouse_counts

DEFAULT_CONFIG = Path('config/quality_rules.json')
DEFAULT_LAKE = Path('data/lake/quality_metrics.json')
DEFAULT_WAREHOUSE = Path('data/warehouse/warehouse_metrics.json')
DEFAULT_DB = Path('data/warehouse/global_logistics.duckdb')
DEFAULT_STREAM = Path('data/stream/consumer_metrics.json')
DEFAULT_REPORT = Path('data/monitor/quality_report.json')
DEFAULT_ALERTS = Path('data/monitor/alerts.jsonl')
DEFAULT_RULES = {
    'minimum_shipments': 1,
    'minimum_unique_events': 1,
    'max_invalid_rate_pct': 5.0,
    'max_duplicate_rate_pct': 10.0,
}
WAREHOUSE_COUNT_FIELDS = (
    'staging_event_rows', 'fact_event_rows', 'staging_shipment_rows',
    'fact_shipment_rows', 'delivered_shipments', 'late_deliveries',
    'distinct_fact_shipments', 'distinct_fact_events',
    'carrier_mart_shipments', 'route_mart_shipments', 'daily_mart_events',
    'orphan_carrier_keys', 'orphan_route_keys',
    'orphan_planned_date_keys', 'orphan_event_date_keys',
)


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'Expected JSON object in {path}')
    return data


def validate_rules(rules: dict) -> None:
    if set(rules) != set(DEFAULT_RULES):
        raise ValueError(f'Config must contain exactly: {", ".join(DEFAULT_RULES)}')
    for key in ('minimum_shipments', 'minimum_unique_events'):
        value = rules[key]
        if type(value) is not int or value < 1:
            raise ValueError(f'{key} must be an integer >= 1')
    for key in ('max_invalid_rate_pct', 'max_duplicate_rate_pct'):
        value = rules[key]
        if type(value) not in (int, float) or not 0 <= value <= 100:
            raise ValueError(f'{key} must be a percentage from 0 to 100')


def check_stream_metrics(metrics: dict) -> None:
    fields = ('received', 'accepted', 'duplicates', 'invalid', 'distinct_shipments')
    for name in fields:
        if type(metrics.get(name)) is not int or metrics[name] < 0:
            raise ValueError(f'Stream metric {name} must be a nonnegative integer')
    if metrics['received'] != metrics['accepted'] + metrics['duplicates'] + metrics['invalid']:
        raise ValueError('stream reconciliation failed: received != accepted + duplicates + invalid')
    if metrics['distinct_shipments'] > metrics['accepted']:
        raise ValueError('stream reconciliation failed: more shipments than accepted records')


def evaluate_quality(lake: dict, warehouse: dict, live: dict,
                     rules: dict, stream: dict | None = None) -> dict:
    """Pure quality checks; returns all failures, does not stop on first failure."""
    errors: list[str] = []
    try:
        validate_rules(rules)
    except ValueError as exc:
        return {'status': 'FAIL', 'failures': [str(exc)], 'measurements': {}}
    try:
        validate_metrics(lake)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f'lake reconciliation: {exc}')
    try:
        validate_warehouse_counts(lake, warehouse)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f'warehouse reconciliation: {exc}')
    try:
        validate_warehouse_counts(lake, live)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f'live database reconciliation: {exc}')
    for name in WAREHOUSE_COUNT_FIELDS:
        if name not in live or type(live[name]) is not int:
            errors.append(f'missing or invalid live database metric: {name}')
        elif name not in warehouse or type(warehouse[name]) is not int:
            errors.append(f'missing or invalid recorded warehouse metric: {name}')
        elif live[name] != warehouse[name]:
            errors.append(f'live DB vs warehouse_metrics mismatch: {name} ({live[name]} != {warehouse[name]})')
    if stream is not None:
        try:
            check_stream_metrics(stream)
        except ValueError as exc:
            errors.append(str(exc))

    measurements: dict[str, Any] = {}
    input_rows, valid_rows = lake.get('input_rows'), lake.get('valid_rows')
    invalid_rows, duplicate_rows = lake.get('invalid_rows'), lake.get('duplicate_event_rows')
    if all(type(v) is int and v >= 0 for v in (input_rows, valid_rows, invalid_rows, duplicate_rows)):
        invalid_pct = invalid_rows * 100 / input_rows if input_rows else 0.0
        duplicate_pct = duplicate_rows * 100 / valid_rows if valid_rows else 0.0
        measurements['invalid_rate_pct'] = round(invalid_pct, 4)
        measurements['duplicate_rate_pct'] = round(duplicate_pct, 4)
        if input_rows == 0:
            errors.append('no input events were processed')
        if invalid_pct > rules['max_invalid_rate_pct']:
            errors.append(f'invalid event rate {invalid_pct:.2f}% > {rules["max_invalid_rate_pct"]}%')
        if duplicate_pct > rules['max_duplicate_rate_pct']:
            errors.append(f'duplicate event rate {duplicate_pct:.2f}% > {rules["max_duplicate_rate_pct"]}%')
    else:
        errors.append('invalid lake metrics needed to calculate rates')
    for metric, threshold in (
        ('gold_distinct_shipments', rules['minimum_shipments']),
        ('silver_unique_event_rows', rules['minimum_unique_events']),
    ):
        value = lake.get(metric)
        if type(value) is not int or value < threshold:
            errors.append(f'{metric} must be >= {threshold}; got {value}')
        else:
            measurements[metric] = value

    return {'status': 'FAIL' if errors else 'PASS', 'failures': errors, 'measurements': measurements}


def live_database_counts(db_path: Path) -> dict[str, int]:
    if not db_path.is_file():
        raise FileNotFoundError(f'Warehouse DB missing: {db_path}. Run Phase 4 warehouse build.')
    from .warehouse import _collect_counts
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError('Install DuckDB: python -m pip install -r requirements-warehouse.txt') from exc
    with duckdb.connect(str(db_path), read_only=True) as con:
        return _collect_counts(con)


def run_quality_check(config: Path = DEFAULT_CONFIG,
                      lake_path: Path = DEFAULT_LAKE,
                      warehouse_path: Path = DEFAULT_WAREHOUSE,
                      db_path: Path = DEFAULT_DB,
                      stream_path: Path = DEFAULT_STREAM,
                      report_path: Path = DEFAULT_REPORT,
                      alerts_path: Path = DEFAULT_ALERTS) -> dict:
    """Always writes an audit report and returns PASS/FAIL; never uploads anything."""
    result: dict[str, Any] = {'status': 'FAIL', 'failures': [], 'measurements': {}}
    try:
        rules = _load_json(config)
        validate_rules(rules)
        lake = _load_json(lake_path)
        warehouse = _load_json(warehouse_path)
        live = live_database_counts(db_path)
        stream = _load_json(stream_path) if stream_path.is_file() else None
        result = evaluate_quality(lake, warehouse, live, rules, stream)
    except Exception as exc:
        # Failure becomes a visible, persisted local report instead of silently passing.
        result['failures'].append(f'{type(exc).__name__}: {exc}')
    result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
    result['source_type'] = 'synthetic_local'
    result['inputs'] = {'lake_metrics': str(lake_path),
                        'warehouse_metrics': str(warehouse_path),
                        'warehouse_db': str(db_path)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = report_path.with_name(report_path.name + '.tmp')
    tmp_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp_path, report_path)
    if result['status'] == 'FAIL':
        alerts_path.parent.mkdir(parents=True, exist_ok=True)
        with alerts_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'checked_at_utc': result['checked_at_utc'],
                                     'failures': result['failures']}) + '\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Offline shipment data-quality monitoring')
    parser.add_argument('command', choices=['check'])
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--lake-metrics', type=Path, default=DEFAULT_LAKE)
    parser.add_argument('--warehouse-metrics', type=Path, default=DEFAULT_WAREHOUSE)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--stream-metrics', type=Path, default=DEFAULT_STREAM)
    parser.add_argument('--report', type=Path, default=DEFAULT_REPORT)
    parser.add_argument('--alerts', type=Path, default=DEFAULT_ALERTS)
    args = parser.parse_args()
    report = run_quality_check(args.config, args.lake_metrics, args.warehouse_metrics,
                               args.db, args.stream_metrics, args.report, args.alerts)
    print(f'QUALITY GATE: {report["status"]}')
    for key, value in report.get('measurements', {}).items():
        print(f'  {key}: {value}')
    for failure in report['failures']:
        print(f'  FAIL: {failure}')
    print(f'Report: {args.report}')
    raise SystemExit(0 if report['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
