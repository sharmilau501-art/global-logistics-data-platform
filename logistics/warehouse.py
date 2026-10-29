"""Phase 4. Build/query an entirely local DuckDB logistics data warehouse.

Reads Spark Parquet lake outputs. Zero AWS SDKs, APIs, or paid resources.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .lake_checks import validate_metrics
from .warehouse_checks import validate_warehouse_counts

DEFAULT_LAKE = Path('data/lake')
DEFAULT_DB = Path('data/warehouse/global_logistics.duckdb')
SQL_FILE = Path(__file__).resolve().parent.parent / 'sql' / 'warehouse.sql'


def _scan_pattern(folder: Path) -> str:
    if not folder.is_dir() or not any(folder.rglob('*.parquet')):
        raise FileNotFoundError(
            f'No Parquet files in {folder}. Run the Phase 3 Spark job successfully first.'
        )
    # DuckDB reads Hive-style event_date=YYYY-MM-DD partitions via this recursive glob.
    # Resolve the path before running queries so Windows current-directory changes don't matter.
    return (folder.resolve() / '**' / '*.parquet').as_posix()


def _rowcount(con, query: str) -> int:
    return int(con.execute(query).fetchone()[0])


def _collect_counts(con) -> dict[str, int]:
    counts_sql = {
        'staging_event_rows': 'SELECT COUNT(*) FROM stg_events',
        'fact_event_rows': 'SELECT COUNT(*) FROM fact_shipment_event',
        'staging_shipment_rows': 'SELECT COUNT(*) FROM stg_shipment_current',
        'fact_shipment_rows': 'SELECT COUNT(*) FROM fact_shipment',
        'delivered_shipments': 'SELECT COUNT(*) FROM fact_shipment WHERE is_delivered',
        'late_deliveries': 'SELECT COUNT(*) FROM fact_shipment WHERE is_late_delivery',
        'distinct_fact_shipments': 'SELECT COUNT(DISTINCT shipment_id) FROM fact_shipment',
        'distinct_fact_events': 'SELECT COUNT(DISTINCT event_id) FROM fact_shipment_event',
        'carrier_mart_shipments': 'SELECT COALESCE(SUM(total_shipments), 0) FROM mart_carrier_performance',
        'route_mart_shipments': 'SELECT COALESCE(SUM(total_shipments), 0) FROM mart_route_performance',
        'daily_mart_events': 'SELECT COALESCE(SUM(event_count), 0) FROM mart_daily_event_volume',
        'orphan_carrier_keys': '''SELECT COUNT(*) FROM fact_shipment f
            LEFT JOIN dim_carrier d ON f.carrier_key=d.carrier_key WHERE d.carrier_key IS NULL''',
        'orphan_route_keys': '''SELECT COUNT(*) FROM fact_shipment f
            LEFT JOIN dim_route d ON f.route_key=d.route_key WHERE d.route_key IS NULL''',
        'orphan_planned_date_keys': '''SELECT COUNT(*) FROM fact_shipment f
            LEFT JOIN dim_date d ON f.planned_delivery_date_key=d.date_key WHERE d.date_key IS NULL''',
        'orphan_event_date_keys': '''SELECT COUNT(*) FROM fact_shipment_event f
            LEFT JOIN dim_date d ON f.event_date_key=d.date_key WHERE d.date_key IS NULL''',
    }
    return {key: _rowcount(con, sql) for key, sql in counts_sql.items()}


def build_warehouse(lake_root: Path = DEFAULT_LAKE, db_path: Path = DEFAULT_DB) -> dict:
    """Build or refresh the warehouse in a transaction, validating before commit."""
    lake_root = Path(lake_root)
    db_path = Path(db_path)
    metrics_path = lake_root / 'quality_metrics.json'
    if not metrics_path.is_file():
        raise FileNotFoundError(f'Missing {metrics_path}. Run the Phase 3 Spark job first.')
    lake_metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    validate_metrics(lake_metrics)

    silver_pattern = _scan_pattern(lake_root / 'silver' / 'shipment_events')
    gold_pattern = _scan_pattern(lake_root / 'gold' / 'shipment_current')
    db_path.parent.mkdir(parents=True, exist_ok=True)

    import duckdb  # installed separately; Phase 1-3 unit tests do not require DuckDB

    with duckdb.connect(str(db_path)) as con:
        con.execute("SET TimeZone = 'UTC'")
        con.execute('BEGIN TRANSACTION')
        try:
            con.execute(
                'CREATE OR REPLACE TABLE stg_events AS '
                'SELECT * FROM read_parquet(?, hive_partitioning = true)',
                [silver_pattern]
            )
            con.execute(
                'CREATE OR REPLACE TABLE stg_shipment_current AS '
                'SELECT * FROM read_parquet(?)', [gold_pattern]
            )
            con.execute(SQL_FILE.read_text(encoding='utf-8'))
            counts = _collect_counts(con)
            validate_warehouse_counts(lake_metrics, counts)
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK')
            raise

    result = {'database': str(db_path), 'lake_source': str(lake_root),
              'source_type': 'synthetic_local', **counts}
    report_path = db_path.parent / 'warehouse_metrics.json'
    report_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def report_warehouse(db_path: Path = DEFAULT_DB) -> None:
    import duckdb
    if not db_path.is_file():
        raise FileNotFoundError(f'Warehouse not found: {db_path}. Run build first.')
    with duckdb.connect(str(db_path), read_only=True) as con:
        summary = con.execute('''
            SELECT COUNT(*) AS total_shipments,
                   COUNT(*) FILTER (WHERE is_delivered) AS delivered_shipments,
                   COUNT(*) FILTER (WHERE is_late_delivery) AS late_deliveries,
                   COUNT(*) FILTER (WHERE had_customs_hold) AS customs_hold_shipments
            FROM fact_shipment
        ''').fetchone()
        print('GLOBAL LOGISTICS: LOCAL SHIPMENT KPIs')
        for label, value in zip(('Total shipments', 'Delivered shipments',
                                 'Late deliveries', 'Customs hold shipments'), summary):
            print(f'  {label}: {value}')
        print('\nCARRIER PERFORMANCE')
        for carrier, shipments, delivered, late, pct in con.execute('''
            SELECT carrier, total_shipments, delivered_shipments,
                   late_deliveries, on_time_delivery_pct
            FROM mart_carrier_performance ORDER BY total_shipments DESC, carrier
        ''').fetchall():
            print(f'  {carrier}: {shipments} shipments, {delivered} delivered, '
                  f'{late} late, {pct}% on-time among delivered')
        print('\nTOP ROUTES BY LATE DELIVERIES')
        for origin, destination, total, late in con.execute('''
            SELECT origin_city, destination_city, total_shipments, late_deliveries
            FROM mart_route_performance
            ORDER BY late_deliveries DESC, total_shipments DESC LIMIT 5
        ''').fetchall():
            print(f'  {origin} -> {destination}: {late} late / {total} total')
    print('\nAll results are synthetic and local. No AWS services were used.')


def main():
    parser = argparse.ArgumentParser(description='Local DuckDB logistics analytics')
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build', help='Build/refresh warehouse and reconcile with lake')
    build.add_argument('--lake-root', type=Path, default=DEFAULT_LAKE)
    build.add_argument('--db', type=Path, default=DEFAULT_DB)
    report = sub.add_parser('report', help='Print shipment and carrier KPIs')
    report.add_argument('--db', type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if args.command == 'build':
        result = build_warehouse(args.lake_root, args.db)
        print(json.dumps(result, indent=2))
        print('PASS: warehouse matches Phase 3 lake metrics. No cloud services used.')
    else:
        report_warehouse(args.db)


if __name__ == '__main__':
    main()
