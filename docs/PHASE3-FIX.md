# Phase 3 fix (Windows PowerShell + Docker)

Fixes two problems in the initial Spark invocation:
1. Remove `--network none` so Spark can resolve its Docker hostname.
2. Run a project-root wrapper (`run_lake.py`) to avoid shadowing Python's standard-library `inspect` with `logistics/inspect.py`.
3. Use the absolute import `logistics.lake_checks` inside `logistics/lake_etl.py`.

Merge this ZIP into the root of your current `global-logistics` project, replacing only `logistics/lake_etl.py` and adding `run_lake.py`.

PowerShell command (one line):

```
docker run --rm --network bridge --hostname spark-local --user 0:0 -e SPARK_LOCAL_IP=127.0.0.1 -v "${PWD}:/workspace" -w /workspace --entrypoint /opt/spark/bin/spark-submit apache/spark:4.1.4-python3 --master "local[2]" /workspace/run_lake.py
```

Then verify:

```
Get-Content .\data\lake\quality_metrics.json
python -m logistics.lake_checks
python -m pytest -q
```

All work remains local, no cloud or AWS resources are used.
