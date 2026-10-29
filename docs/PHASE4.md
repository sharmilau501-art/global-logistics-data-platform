# Phase 4: DuckDB Warehouse & Operational KPIs ($0 cloud costs)

Phase 4 reads the **existing Phase 3 Silver and Gold Parquet datasets** and builds a *local* DuckDB database. There are no AWS services, remote models, or other paid APIs. It also checks dimensional relationships and compares fact/mart totals with `data/lake/quality_metrics.json`.

## Prerequisite

- Complete Phase 3 and confirm `data/lake/quality_metrics.json` exists.
- Keep working in PowerShell from `C:\Users\uppal\projects\global-logistics` with `.venv` active.
- No Docker, Kafka, Java, or running Spark containers are needed for Phase 4 after Parquet files exist.
- Python 3.14 is supported by current DuckDB Python packages.

## Commands

```powershell
cd "C:\Users\uppal\projects\global-logistics"
python -m pip install -r requirements-warehouse.txt
python -m logistics.warehouse build
python -m logistics.warehouse report
Get-Content .\data\warehouse\warehouse_metrics.json
python -m pytest -q
```

The results are stored in `data/warehouse/global_logistics.duckdb` and `data/warehouse/warehouse_metrics.json`. You can rebuild any time. A build uses a transaction and rolls back the SQL changes on error.

## Tables built

| Name | Grain |
|---|---|
| `stg_events` | Unique Silver event |
| `stg_shipment_current` | Gold current shipment |
| `dim_carrier` | Carrier |
| `dim_route` | Origin-destination route |
| `dim_date` | Calendar day |
| `fact_shipment` | One row per shipment |
| `fact_shipment_event` | One row per event |
| `mart_carrier_performance` | Carrier |
| `mart_route_performance` | Route |
| `mart_daily_event_volume` | Event day and event type |

**Metric definition:** On-time delivery percentage = (delivered - late delivered) / delivered × 100. Undelivered shipments are excluded from that percentage. A shipment is late if `delivered_time > planned_delivery_time`. Results reflect the synthetic source events you processed, which may include only a small Kafka batch.

## Debugging

- `No Parquet files...`: confirm the Phase 3 Docker job succeeded, and that `data/lake/silver/shipment_events/` and `data/lake/gold/shipment_current/` each contain `.parquet` files.
- `No module named duckdb`: activate `.venv` and install `requirements-warehouse.txt` in that environment.
- `warehouse ... mismatch`: a real integrity failure; do not change expected counts to force a pass. Confirm Phase 3 outputs and metrics were created in the same run.
- `database is locked`: close any DuckDB UI/notebook session using the DB file and rerun the build.

## Portfolio accuracy

This demonstrates local DuckDB SQL modeling, Parquet ingestion, dimensional models, metrics marts, reconciliation and data quality. It is **not** an actual Amazon Redshift deployment.
