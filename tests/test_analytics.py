"""Analytics validation and optional end-to-end DuckDB integration tests."""
from pathlib import Path
from unittest.mock import patch
import pytest

from logistics.analytics import get_filters, load_dashboard, _records


def test_requires_existing_warehouse(tmp_path):
    with pytest.raises(FileNotFoundError, match='Warehouse not found'):
        load_dashboard(tmp_path / 'absent.duckdb')


@pytest.mark.parametrize('carrier,route_key', [('', None), (42, None), (None, 0), (None, True), (None, '1')])
def test_rejects_invalid_filter_inputs(carrier, route_key):
    with pytest.raises(ValueError):
        load_dashboard(Path('does-not-matter.duckdb'), carrier, route_key)


class FakeCursor:
    description = [('shipment_id',), ('late',)]
    def fetchall(self): return [('SHIP-1', 1)]


class FakeConnection:
    def __init__(self): self.statement = None; self.params = None
    def execute(self, sql, params):
        self.statement = sql; self.params = params
        return FakeCursor()


def test_records_binds_sql_params():
    con = FakeConnection()
    result = _records(con, 'SELECT shipment_id, late FROM t WHERE name = ?', ['A'])
    assert con.params == ['A']
    assert result == [{'shipment_id': 'SHIP-1', 'late': 1}]


def test_synthetic_duckdb_snapshot(tmp_path):
    duckdb = pytest.importorskip('duckdb')
    db = tmp_path / 'test.duckdb'
    with duckdb.connect(str(db)) as con:
        con.execute("""CREATE TABLE dim_carrier AS SELECT * FROM (VALUES
            (1,'CARRIER_A'),(2,'CARRIER_B')) AS c(carrier_key,carrier)""")
        con.execute("""CREATE TABLE dim_route AS SELECT * FROM (VALUES
            (1,'Shanghai','China','Los Angeles','United States'),
            (2,'Mumbai','India','New York','United States'))
            AS r(route_key,origin_city,origin_country,destination_city,destination_country)""")
        con.execute("""CREATE TABLE fact_shipment AS SELECT * FROM (VALUES
            ('SHIP-1',1,1,true,true,true,'DELIVERED', TIMESTAMP '2026-10-03 08:00'),
            ('SHIP-2',1,1,true,false,false,'DELIVERED', TIMESTAMP '2026-10-04 08:00'),
            ('SHIP-3',2,2,false,false,true,'CUSTOMS_HOLD',TIMESTAMP '2026-10-05 08:00'))
            AS f(shipment_id,carrier_key,route_key,is_delivered,is_late_delivery,had_customs_hold,
            latest_event_type, latest_event_time)""")
        con.execute("""CREATE TABLE fact_shipment_event AS SELECT * FROM (VALUES
            ('SHIP-1',TIMESTAMP '2026-10-03 08:00','WEATHER'),
            ('SHIP-1',TIMESTAMP '2026-10-04 08:00','WEATHER'),
            ('SHIP-2',TIMESTAMP '2026-10-04 08:00',NULL),
            ('SHIP-3',TIMESTAMP '2026-10-05 08:00','CUSTOMS'))
            AS e(shipment_id,event_time,delay_reason)""")

    opts = get_filters(db)
    assert opts['carriers'] == ['CARRIER_A', 'CARRIER_B']
    assert len(opts['routes']) == 2
    snap = load_dashboard(db)
    assert snap['overview']['shipments'] == 3
    assert snap['overview']['delivered'] == 2
    assert snap['overview']['late'] == 1
    assert snap['overview']['customs_holds'] == 2
    assert snap['overview']['on_time_pct'] == 50.0
    assert len(snap['delay_reasons']) == 2
    assert next(r for r in snap['delay_reasons'] if r['delay_reason'] == 'WEATHER')['affected_shipments'] == 1
    assert sum(r['shipments'] for r in snap['carriers']) == 3
    assert sum(r['events'] for r in snap['daily_events']) == 4
    assert all(isinstance(r['event_date'], str) for r in snap['daily_events'])
    assert len(snap['exceptions']) == 2
    a = load_dashboard(db, carrier='CARRIER_A')
    assert a['overview']['shipments'] == 2
    assert a['overview']['late'] == 1
    r = load_dashboard(db, route_key=2)
    assert r['overview']['shipments'] == 1
    assert r['overview']['delivered'] == 0
    assert r['overview']['on_time_pct'] is None
    empty = load_dashboard(db, carrier='UNKNOWN')
    assert empty['overview']['shipments'] == 0
    assert empty['carriers'] == []
