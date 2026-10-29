# Phase 3: Local PySpark Data Lake

**Strictly $0 cloud usage.** Spark executes inside a Docker container on your Windows PC. No cloud credentials, credit cards, cloud APIs, or paid models required.

## Preconditions

- Phase 1 synthetic data generated.
- Phase 2 consumer executed successfully, producing `data/stream/unique_shipment_events.jsonl`.
- Docker Desktop running.
- PowerShell working directory: `C:\Users\uppal\projects\global-logistics`.

## 1. Validate local files

```powershell
Test-Path .\data\stream\unique_shipment_events.jsonl
Test-Path .\logistics\lake_etl.py
```

If the Phase 2 stream output is missing, you can process Phase 1 raw data instead; use the fallback `--input` option below. Note that raw data includes replay duplicates, so it is useful for testing deduplication.

## 2. Run local Apache Spark in Docker

This image is large (~0.8 GB to download compressed). It downloads to your PC and does not create AWS charges. It runs only when invoked. The Docker command mounts the current project directory into `/workspace` and disables container networking; Spark operates entirely locally.

```powershell
docker run --rm --network none --user 0:0 -e SPARK_LOCAL_IP=127.0.0.1 -v "${PWD}:/workspace" -w /workspace --entrypoint /opt/spark/bin/spark-submit apache/spark:4.1.4-python3 --master "local[2]" /workspace/logistics/lake_etl.py
```

**To test deduplication against all raw Phase 1 records**, use the alternative:

```powershell
docker run --rm --network none --user 0:0 -e SPARK_LOCAL_IP=127.0.0.1 -v "${PWD}:/workspace" -w /workspace --entrypoint /opt/spark/bin/spark-submit apache/spark:4.1.4-python3 --master "local[2]" /workspace/logistics/lake_etl.py --input data/raw/shipment_events.jsonl
```

**Note:** Running either command overwrites the previous `data/lake` Parquet outputs. It does not touch Kafka or original JSONL source files. If Docker reports an invalid mount configuration, use `-v "${PWD}.Path:/workspace"` after assigning `$projectPath = (Get-Location).Path`, and use `-v "${projectPath}:/workspace"`.

## 3. Inspect outputs

```powershell
Get-Content .\data\lake\quality_metrics.json
python -m logistics.lake_checks
python -m pytest -q
Get-ChildItem .\data\lake -Recurse | Select-Object -First 30 FullName
```

Folders produced:

- `data/lake/bronze/shipment_events/` : original parsed events in Parquet, partitioned by `ingest_date`
- `data/lake/quarantine/events/` : malformed or invalid events, JSON
- `data/lake/silver/shipment_events/` : unique validated events, Parquet partitioned by `event_date`
- `data/lake/gold/shipment_current/` : current shipment statuses and delivery/delay metrics, Parquet
- `data/lake/quality_metrics.json` : source-to-target reconciliation

## Local tests

The Phase 3 quality-check tests do not need PySpark or Java. Spark pipeline execution is verified only after you run the Docker command. The number of unit tests increases by 8 from Phase 2, from 9 to 17.

## Cost / resume truthfulness

- $0 AWS charges; software and compute run on your own PC.
- This is **local PySpark + Parquet**, not actual AWS Glue, S3, or Redshift deployment.
- Do not claim production AWS operation from this project.
