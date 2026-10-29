# Phase 2: Stream synthetic shipments into a local Apache Kafka broker

No AWS account, payment method, hosted Kafka, or paid API is used. Requires Docker Desktop (Linux containers) and your Phase 1 Python project. Run all commands in **Windows PowerShell** from `C:\Users\uppal\projects\global-logistics`.

## Install files

Extract the Phase 2 ZIP **into the existing project directory**, keeping its `logistics/`, `tests/`, and `docs/` subdirectories. Do not create a second nested project directory.

## Start Docker and Kafka

```powershell
cd "C:\Users\uppal\projects\global-logistics"
docker --version
docker compose version
docker compose up -d
docker compose ps
```

First-time startup downloads the official Docker image (free). It can take a moment to initialize. Kafka's single-node KRaft setup listens on `127.0.0.1:9092` on the host. Port binding is local-only and plaintext; do not expose it to the internet.

Create topic (after the broker has started):

```powershell
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:19092 --create --if-not-exists --topic shipment-events --partitions 3 --replication-factor 1
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:19092 --list
```

## Install client and run

You can use your activated venv, or the following unambiguous path to the venv's Python interpreter:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-stream.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m logistics.generator --shipments 200 --seed 42
.\.venv\Scripts\python.exe -m logistics.stream_producer --limit 50
.\.venv\Scripts\python.exe -m logistics.stream_consumer --idle-seconds 5
```

Check resulting `data/stream/consumer_metrics.json` and `data/stream/unique_shipment_events.jsonl`. Replays and duplicate shipment event IDs are deduplicated. The messages are deliberately shuffled, so don't assume chronological arrival.

To publish all shipment events instead of a 50-event quick run:

```powershell
.\.venv\Scripts\python.exe -m logistics.stream_producer
.\.venv\Scripts\python.exe -m logistics.stream_consumer --idle-seconds 5
```

The second run consumes earlier messages too, because each run uses a new Kafka consumer group and starts at earliest. That's deliberate for repeatable learning runs. The unique output gets replaced each run. Phase 3 will improve stateful checkpointing and persistence.

## Cleanup

```powershell
docker compose down
```

This stops/removes the Kafka container (and because there is no persistent volume configured, Kafka's streamed messages disappear). The locally generated Phase 1 and consumer output files remain. Docker Hub download and ordinary Python packages are free; no cloud-service billing occurs.

## Troubleshooting

- `docker` not recognized: install or start Docker Desktop with Linux containers enabled.
- Docker engine unavailable: start Docker Desktop, then retry `docker compose ps`.
- `Connection refused` / no broker: check `docker compose ps`, `docker compose logs kafka`, and wait until startup completes.
- Topic missing: run the `kafka-topics.sh --create` command shown above.
- Port 9092 in use: stop the other Kafka container/service first. Avoid running two brokers on the same port.
- `ModuleNotFoundError: No module named kafka`: install `requirements-stream.txt` with the venv's Python.

## Technical boundaries

The Phase 2 consumer deduplicates **within a run**, not across restarts. The producer uses broker acknowledgments, but not end-to-end exactly-once guarantees. This is a local streaming simulation (Kafka), not AWS Kinesis deployment.
