"""Real local DuckDB integration smoke test. Skips until DuckDB is installed."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_build_warehouse_from_real_local_parquet(tmp_path: Path):
    duckdb = pytest.importorskip('duckdb')
    from logistics.warehouse import build_warehouse

    lake = tmp_path / 'lake'
    silver = lake / 'silver' / 'shipment_events'
    gold = lake / 'gold' / 'shipment_current'
    silver.mkdir(parents=True)
    gold.mkdir(parents=True)

    def escape(path: Path) -> str:
        return path.as_posix().replace("'", "''")

    with duckdb.connect(':memory:') as con:
        con.execute(f"""
            COPY (
              SELECT * FROM (VALUES
                ('event-1', 'ship-1', 'CREATED',
                 TIMESTAMP '2026-10-01 08:00:00', TIMESTAMP '2026-10-01 08:01:00',
                 CAST(NULL AS VARCHAR), 'synthetic'),
                ('event-2', 'ship-1', 'DELIVERED',
                 TIMESTAMP '2026-10-07 08:00:00', TIMESTAMP '2026-10-07 08:01:00',
                 'PORT_CONGESTION', 'synthetic'),
                ('event-3', 'ship-2', 'CREATED',
                 TIMESTAMP '2026-10-02 08:00:00', TIMESTAMP '2026-10-02 08:01:00',
                 CAST(NULL AS VARCHAR), 'synthetic')
              ) AS events(event_id, shipment_id, event_type, event_time,
                          ingest_time, delay_reason, source_system)
            ) TO '{escape(silver / 'part-00000.parquet')}' (FORMAT PARQUET)
        """)
        con.execute(f"""
            COPY (
              SELECT * FROM (VALUES
                ('ship-1', 'CARRIER_A', 'Shanghai', 'China', 'Seattle', 'United States',
                 120.0, TIMESTAMP '2026-10-06 08:00:00', 'DELIVERED',
                 TIMESTAMP '2026-10-07 08:00:00', 2,
                 TIMESTAMP '2026-10-07 08:00:00', 0, TRUE),
                ('ship-2', 'CARRIER_B', 'Mumbai', 'India', 'New York', 'United States',
                 80.0, TIMESTAMP '2026-10-08 08:00:00', 'CREATED',
                 TIMESTAMP '2026-10-02 08:00:00', 1,
                 CAST(NULL AS TIMESTAMP), 0, CAST(NULL AS BOOLEAN))
              ) AS shipments(shipment_id, carrier, origin_city, origin_country,
                  destination_city, destination_country, weight_kg,
                  planned_delivery_time, latest_event_type, latest_event_time,
                  observed_event_count, delivered_time, had_customs_hold, is_late_delivery)
            ) TO '{escape(gold / 'part-00000.parquet')}' (FORMAT PARQUET)
        """)

    lake_metrics = {
        'input_rows': 3, 'valid_rows': 3, 'invalid_rows': 0,
        'duplicate_event_rows': 0, 'silver_unique_event_rows': 3,
        'gold_distinct_shipments': 2, 'delivered_shipments': 1, 'late_deliveries': 1,
    }
    (lake / 'quality_metrics.json').write_text(json.dumps(lake_metrics), encoding='utf-8')
    db = tmp_path / 'warehouse' / 'global_logistics.duckdb'
    counts = build_warehouse(lake, db)
    assert counts['fact_shipment_rows'] == 2
    assert counts['fact_event_rows'] == 3
    assert counts['late_deliveries'] == 1
    assert (db.parent / 'warehouse_metrics.json').is_file()

    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute('SELECT COUNT(*) FROM dim_date').fetchone()[0] >= 3
        assert con.execute('SELECT SUM(total_shipments) FROM mart_carrier_performance').fetchone()[0] == 2
        assert con.execute('SELECT SUM(event_count) FROM mart_daily_event_volume').fetchone()[0] == 3

    # A repeat build is idempotent; table counts must not double.
    counts2 = build_warehouse(lake, db)
    assert counts2['fact_shipment_rows'] == 2
