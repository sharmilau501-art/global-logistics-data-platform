"""Read-only, parameterized logistics dashboard queries against the local DuckDB warehouse.

All metrics are calculated from synthetic local project data. No network calls.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_DB = Path('data/warehouse/global_logistics.duckdb')


def _connect(db_path: Path):
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(f'Warehouse not found: {db_path}. Run: python -m logistics.warehouse build')
    import duckdb
    con = duckdb.connect(str(db_path), read_only=True)
    con.execute("SET TimeZone = 'UTC'")
    return con


def _records(con, sql: str, params: list | None = None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [column[0] for column in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_filters(db_path: Path = DEFAULT_DB) -> dict:
    with _connect(db_path) as con:
        carriers = [row[0] for row in con.execute('SELECT carrier FROM dim_carrier ORDER BY carrier').fetchall()]
        routes = _records(con, '''SELECT route_key, origin_city, origin_country,
                                         destination_city, destination_country
                                  FROM dim_route ORDER BY origin_country, origin_city,
                                  destination_country, destination_city''')
    for route in routes:
        route['label'] = (f"{route['origin_city']}, {route['origin_country']} → "
                          f"{route['destination_city']}, {route['destination_country']}")
    return {'carriers': carriers, 'routes': routes}


def load_dashboard(db_path: Path = DEFAULT_DB, carrier: str | None = None,
                   route_key: int | None = None) -> dict:
    """Build an internally consistent filtered snapshot using bound parameters only."""
    if carrier is not None and (not isinstance(carrier, str) or not carrier.strip()):
        raise ValueError('carrier must be a nonempty string or None')
    if route_key is not None and (type(route_key) is not int or route_key < 1):
        raise ValueError('route_key must be a positive integer or None')

    # The scoped shipment IDs are the shared grain of ALL metrics and charts.
    filtered = '''WITH scoped AS (
        SELECT f.*, c.carrier, r.origin_city, r.origin_country,
               r.destination_city, r.destination_country
        FROM fact_shipment f
        JOIN dim_carrier c ON c.carrier_key = f.carrier_key
        JOIN dim_route r ON r.route_key = f.route_key
        WHERE (? IS NULL OR c.carrier = ?)
          AND (? IS NULL OR f.route_key = ?)
    ) '''
    args = [carrier, carrier, route_key, route_key]
    with _connect(db_path) as con:
        overview = _records(con, filtered + '''SELECT
            COUNT(*) AS shipments,
            COUNT(*) FILTER (WHERE is_delivered) AS delivered,
            COUNT(*) FILTER (WHERE is_late_delivery) AS late,
            COUNT(*) FILTER (WHERE had_customs_hold) AS customs_holds,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_delivered AND NOT is_late_delivery)
               / NULLIF(COUNT(*) FILTER (WHERE is_delivered), 0), 2) AS on_time_pct
            FROM scoped''', args)[0]
        carriers = _records(con, filtered + '''SELECT carrier, COUNT(*) AS shipments,
            COUNT(*) FILTER (WHERE is_delivered) AS delivered,
            COUNT(*) FILTER (WHERE is_late_delivery) AS late,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_delivered AND NOT is_late_delivery)
                / NULLIF(COUNT(*) FILTER (WHERE is_delivered), 0), 2) AS on_time_pct
            FROM scoped GROUP BY carrier ORDER BY shipments DESC, carrier''', args)
        routes = _records(con, filtered + '''SELECT
            origin_city, origin_country, destination_city, destination_country,
            COUNT(*) AS shipments, COUNT(*) FILTER (WHERE is_late_delivery) AS late,
            ROUND(100.0 * COUNT(*) FILTER (WHERE is_delivered AND NOT is_late_delivery)
                / NULLIF(COUNT(*) FILTER (WHERE is_delivered), 0), 2) AS on_time_pct
            FROM scoped GROUP BY ALL ORDER BY late DESC, shipments DESC,
                 origin_city, destination_city''', args)
        # DISTINCT prevents the same shipment/delay reason from being double-counted
        # when the generator marks both an arrival and a delivery event.
        delays = _records(con, filtered + '''SELECT delay_reason,
               COUNT(*) AS affected_shipments FROM (
                 SELECT DISTINCT e.shipment_id, e.delay_reason
                 FROM fact_shipment_event e
                 JOIN scoped s ON s.shipment_id = e.shipment_id
                 WHERE e.delay_reason IS NOT NULL AND e.delay_reason <> ''
               ) d GROUP BY delay_reason ORDER BY affected_shipments DESC, delay_reason''', args)
        daily = _records(con, filtered + '''SELECT CAST(e.event_time AS DATE) AS event_date,
            COUNT(*) AS events FROM fact_shipment_event e
            JOIN scoped s ON e.shipment_id = s.shipment_id
            GROUP BY CAST(e.event_time AS DATE) ORDER BY event_date''', args)
        status = _records(con, filtered + '''SELECT latest_event_type AS status,
            COUNT(*) AS shipments FROM scoped
            GROUP BY latest_event_type ORDER BY shipments DESC, status''', args)
        exceptions = _records(con, filtered + '''SELECT shipment_id, carrier,
            origin_city, destination_city, latest_event_type,
            CAST(latest_event_time AS VARCHAR) AS latest_event_time,
            is_late_delivery, had_customs_hold
            FROM scoped WHERE is_late_delivery OR had_customs_hold OR NOT is_delivered
            ORDER BY is_late_delivery DESC, had_customs_hold DESC,
                     latest_event_time DESC, shipment_id LIMIT 100''', args)
    for item in routes:
        item['route'] = (f"{item['origin_city']}, {item['origin_country']} → "
                         f"{item['destination_city']}, {item['destination_country']}")
    for item in daily:
        item['event_date'] = str(item['event_date'])
    return {'source': 'synthetic_local', 'filters': {'carrier': carrier, 'route_key': route_key},
            'overview': overview, 'carriers': carriers, 'routes': routes,
            'delay_reasons': delays, 'daily_events': daily,
            'status_distribution': status, 'exceptions': exceptions}


def main() -> None:
    parser = argparse.ArgumentParser(description='Read-only, offline logistics KPIs')
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--carrier', default=None)
    parser.add_argument('--route-key', type=int, default=None)
    args = parser.parse_args()
    snapshot = load_dashboard(args.db, args.carrier, args.route_key)
    print(json.dumps(snapshot, indent=2, default=str))
    print('Source: synthetic local DuckDB; network calls: none')


if __name__ == '__main__':
    main()
