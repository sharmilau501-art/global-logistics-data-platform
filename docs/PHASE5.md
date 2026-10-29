# Phase 5: Offline quality monitoring, bounded retry, and local CI-style checks

This is an **addition to your working Phase 4 project**. There are **no AWS SDKs, paid APIs, GitHub Actions runners, or remote services**. Run in your current Windows PowerShell `.venv`.

## What is implemented

- Quality gate that reuses Phase 3 lake and Phase 4 warehouse reconciliation invariants.
- Independent read of **live** DuckDB fact/mart counts. The saved `warehouse_metrics.json` alone cannot make a corrupted DB pass.
- Configurable thresholds for invalid and duplicate event rates and minimum input volume (`config/quality_rules.json`).
- Optional independent Kafka consumer metrics reconciliation when `data/stream/consumer_metrics.json` is present.
- Local JSON audit report, failure history, non-zero process exit when checks fail.
- Transactional/idempotent Phase 4 warehouse rebuild with limited retry on **transient** lock or OS errors only. Bad data, missing files, and quality failures must not be retried away.
- PowerShell local CI-style gate: tests -> warehouse refresh -> monitor.

## PowerShell commands

```powershell
cd "C:\Users\uppal\projects\global-logistics"
python -m pytest -q
python -m logistics.quality_monitor check
Get-Content .\data\monitor\quality_report.json
python -m logistics.warehouse_runner --max-attempts 3 --retry-delay 1
.\scripts\phase5-check.ps1
```

If PowerShell blocks `.ps1` execution, run each command separately rather than changing the machine-wide execution policy. To grant permission to *this session only*, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## Failure drill (no actual data is modified)

The included unit tests inject corrupt fake metrics and ensure the validator detects count, orphan-key, invalid-rate, and stream-reconciliation failures. Run `python -m pytest -q tests/test_quality_monitor.py tests/test_warehouse_runner.py` to demonstrate negative test cases without damaging your warehouse.

## Important constraints

- Source is synthetic, not Amazon's data.
- All files are local. The `data/monitor/quality_report.json` and `data/monitor/alerts.jsonl` are audit artifacts; nothing is emailed or uploaded.
- A passing quality gate requires a successful Phase 3 Spark run and Phase 4 DuckDB build. If you rebuild the lake after building the warehouse, rebuild the warehouse and run the monitor again.
- `max_invalid_rate_pct` and `max_duplicate_rate_pct` thresholds are project demo settings, not universally acceptable SLAs.
- No built-in scheduled daemon. Run the PowerShell script when you want to validate, or configure Windows Task Scheduler yourself if needed.
- This verifies data quality and model integrity; it is not a production uptime SLA or evidence of AWS/Redshift/CloudWatch operation.

## Resume-safe description (only after actual local execution)

"Added offline pipeline observability and automated quality gates to a synthetic logistics lakehouse, including source-to-warehouse reconciliation, live dimensional-integrity checks, exception logs, and bounded retry handling for transient warehouse failures."
