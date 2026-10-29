"""Fail-closed quality tests; no internet/AWS/DuckDB dependency."""
import json
from pathlib import Path

import pytest

from logistics import quality_monitor as q


def fixture_data():
    lake = {
        'input_rows': 110, 'valid_rows': 108, 'invalid_rows': 2,
        'duplicate_event_rows': 8, 'silver_unique_event_rows': 100,
        'gold_distinct_shipments': 15, 'delivered_shipments': 12,
        'late_deliveries': 3,
    }
    recorded = {
        'staging_event_rows':100, 'fact_event_rows':100,
        'staging_shipment_rows':15, 'fact_shipment_rows':15,
        'delivered_shipments':12, 'late_deliveries':3,
        'distinct_fact_shipments':15, 'distinct_fact_events':100,
        'carrier_mart_shipments':15, 'route_mart_shipments':15, 'daily_mart_events':100,
        'orphan_carrier_keys':0, 'orphan_route_keys':0,
        'orphan_planned_date_keys':0, 'orphan_event_date_keys':0,
    }
    stream = {'received': 110, 'accepted':100, 'duplicates':8,
              'invalid':2, 'distinct_shipments':15}
    return lake, recorded, stream


def test_valid_quality_gate():
    lake, warehouse, stream = fixture_data()
    result = q.evaluate_quality(lake,warehouse,warehouse.copy(),q.DEFAULT_RULES,stream)
    assert result['status']=='PASS'
    assert result['failures']==[]
    assert result['measurements']['invalid_rate_pct']==round(200/110,4)


def test_bad_reconciliation_fails():
    lake, warehouse, stream = fixture_data()
    lake['silver_unique_event_rows'] = 101
    result = q.evaluate_quality(lake, warehouse, warehouse, q.DEFAULT_RULES, stream)
    assert result['status'] == 'FAIL'
    assert any('silver reconciliation' in x for x in result['failures'])


def test_invalid_event_rate_fails():
    lake, warehouse, stream = fixture_data()
    lake.update(input_rows=120, valid_rows=108, invalid_rows=12)
    result = q.evaluate_quality(lake, warehouse, warehouse, q.DEFAULT_RULES)
    assert result['status']=='FAIL'
    assert any('invalid event rate' in x for x in result['failures'])


def test_duplicate_event_rate_fails():
    lake, warehouse, stream = fixture_data()
    lake.update(input_rows=170, valid_rows=168, duplicate_event_rows=68)
    result=q.evaluate_quality(lake,warehouse,warehouse,q.DEFAULT_RULES)
    assert result['status']=='FAIL'
    assert any('duplicate event rate' in x for x in result['failures'])


def test_orphan_key_fails():
    lake, warehouse, stream=fixture_data()
    warehouse['orphan_route_keys'] = 1
    result=q.evaluate_quality(lake,warehouse,warehouse.copy(),q.DEFAULT_RULES)
    assert result['status']=='FAIL'
    assert any('orphan_route_keys' in x for x in result['failures'])


def test_stale_warehouse_metrics_detected_against_live_db():
    lake, warehouse, stream=fixture_data()
    live=warehouse.copy()
    live['fact_shipment_rows']=14
    result=q.evaluate_quality(lake,warehouse,live,q.DEFAULT_RULES)
    assert result['status']=='FAIL'
    assert any('live DB vs warehouse_metrics mismatch' in x for x in result['failures'])


def test_corrupt_stream_metrics_fail():
    lake, warehouse, stream=fixture_data()
    stream['received']=15
    result=q.evaluate_quality(lake,warehouse,warehouse,q.DEFAULT_RULES,stream)
    assert result['status']=='FAIL'
    assert any('stream reconciliation' in x for x in result['failures'])


def test_invalid_rule_types_rejected():
    bad={**q.DEFAULT_RULES,'minimum_shipments':True}
    with pytest.raises(ValueError):q.validate_rules(bad)
    bad={**q.DEFAULT_RULES,'max_invalid_rate_pct':105}
    with pytest.raises(ValueError):q.validate_rules(bad)


def test_missing_metrics_write_fail_report_and_alert(tmp_path):
    report=tmp_path/'monitor'/'report.json'
    alerts=tmp_path/'monitor'/'alerts.jsonl'
    result=q.run_quality_check(
        config=tmp_path/'missing_rules.json',
        lake_path=tmp_path/'missing_lake.json',
        warehouse_path=tmp_path/'missing_warehouse.json',
        db_path=tmp_path/'missing.duckdb',
        stream_path=tmp_path/'missing_stream.json',
        report_path=report, alerts_path=alerts,
    )
    assert result['status']=='FAIL'
    assert len(result['failures'])==1
    assert json.loads(report.read_text())['status']=='FAIL'
    assert len(alerts.read_text().splitlines())==1


def test_successful_monitor_creates_report_no_alert(tmp_path,monkeypatch):
    lake, warehouse, stream=fixture_data()
    files={}
    for name, obj in [('config', q.DEFAULT_RULES),('lake',lake),('warehouse',warehouse),('stream',stream)]:
        p=tmp_path/(name+'.json')
        p.write_text(json.dumps(obj))
        files[name]=p
    monkeypatch.setattr(q,'live_database_counts',lambda _:warehouse.copy())
    report=tmp_path/'monitor'/'report.json'
    alerts=tmp_path/'monitor'/'alerts.jsonl'
    result=q.run_quality_check(files['config'],files['lake'],files['warehouse'],tmp_path/'db.duckdb',
                               files['stream'],report,alerts)
    assert result['status']=='PASS'
    assert json.loads(report.read_text())['status']=='PASS'
    assert not alerts.exists()


def test_stream_optional():
    lake, warehouse, _=fixture_data()
    assert q.evaluate_quality(lake,warehouse,warehouse,q.DEFAULT_RULES)['status']=='PASS'


def test_no_live_db_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        q.live_database_counts(tmp_path/'missing.duckdb')
