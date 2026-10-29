# Global Logistics Data Lake & Shipment Analytics Platform

**Local-first, $0 cloud spend | Python · Kafka · PySpark · Parquet · DuckDB · Streamlit**

A portfolio-grade data engineering project that simulates international shipment
movements and processes synthetic, sometimes duplicated or out-of-order events
through streaming, a medallion lake, a dimensional warehouse, reconciliation and
self-service logistics analytics. **This is not an Amazon project, is not
production-hosted, and does not use AWS services.**

## Architecture

```text
Python synthetic shipment event generator
              |
              v
Apache Kafka broker (Docker) + Python validation/dedup consumer
              |
              v
Local JSONL -> PySpark -> Parquet medallion data lake
              |             bronze / silver / gold
              v
DuckDB SQL warehouse (facts, dimensions, KPIs)
              |
              +----> Quality monitoring, reconciliation and retry checks
              |
              +----> Streamlit dashboard + read-only metric assistant
```

## Implemented modules

| Phase | Capability |
|-------|------------|
| 1 | Deterministic synthetic shipments, malformed/duplicate event tests |
| 2 | Kafka event ingestion and consumer-side validation/deduplication |
| 3 | PySpark local lake ingestion and Silver/Gold Parquet data |
| 4 | DuckDB dimensional warehouse and carrier/route performance marts |
| 5 | Automated reconciliation, quality gates, error handling and retries |
| 6 | Streamlit dashboard and read-only, metrics-grounded assistant |
| 7 | Reproducible container test environment and optional GitHub Actions CI |

## Quick verification (Windows PowerShell)

Use Python 3.14 and your existing `.venv`:

```powershell
python -m pip install -r requirements-stream.txt -r requirements-warehouse.txt -r requirements-dashboard.txt
python -m pytest -q
.\scripts\phase7-check.ps1
python -m streamlit run dashboard.py
```

The local quality checks and dashboard need the data lake and warehouse generated
by previous phases. Unit and integration tests generate independent fixtures.

## Self-contained tests in Docker

```powershell
docker build -f Dockerfile.test -t global-logistics-tests .
docker run --rm --network none global-logistics-tests
```

## Docs

Read `docs/PHASE6.md` for dashboard details and `docs/PHASE7.md` for GitHub setup,
quality checks, and resume-safe project descriptions. Previous phase docs are
available in `docs/`.

## Scope and privacy

- Data is synthetic, not shipment customer data.
- AWS charges: **$0**. No AWS access credentials, paid cloud accounts, or paid APIs.
- Kafka and PySpark run locally; DuckDB uses local disk.
- Default assistant is deterministic and does not call a hosted LLM.
- CI workflow is optional; cloud-hosted runners may be subject to plan limits.
- This project demonstrates *analogous concepts* to Kinesis/S3/Glue/Redshift,
  not hands-on operation of those AWS services.
