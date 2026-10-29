"""Local-only PySpark lake: Kafka consumer JSONL -> bronze/silver/gold Parquet.

Requires a Spark runtime (e.g. the free Apache Spark Docker image).
No connections to cloud providers or paid APIs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_schema():
    from pyspark.sql.types import DoubleType, StringType, StructField, StructType

    string_fields = (
        "event_id", "shipment_id", "event_type", "event_timestamp",
        "ingested_timestamp", "origin_city", "origin_country",
        "destination_city", "destination_country", "carrier",
        "planned_delivery_timestamp", "delay_reason", "source_system",
    )
    fields = [StructField(name, StringType(), True) for name in string_fields]
    fields.append(StructField("weight_kg", DoubleType(), True))
    fields.append(StructField("_corrupt_record", StringType(), True))
    return StructType(fields)


def process(spark, input_path: Path, output_root: Path) -> dict:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    input_path = Path(input_path)
    output_root = Path(output_root)
    if not input_path.is_file():
        raise FileNotFoundError(
            f"Input not found: {input_path}. Run the Kafka consumer first, or pass --input data/raw/shipment_events.jsonl"
        )

    # Explicit schema prevents unpredictable inference and captures bad JSON.
    source = (spark.read.option("mode", "PERMISSIVE")
              .schema(build_schema()).json(str(input_path)))
    # Materialize a copy; Spark disallows filtering only the _corrupt_record field
    # directly on raw JSON in some versions.
    parsed = (source.withColumn("event_time", F.try_to_timestamp("event_timestamp"))
              .withColumn("ingest_time", F.try_to_timestamp("ingested_timestamp"))
              .withColumn("planned_delivery_time", F.try_to_timestamp("planned_delivery_timestamp"))
              .withColumn("ingest_date", F.to_date("ingest_time"))
              .withColumn("event_date", F.to_date("event_time"))
              .cache())
    input_rows = parsed.count()
    if input_rows == 0:
        raise ValueError(f"No events found in {input_path}")

    (parsed.drop("_corrupt_record")
     .write.mode("overwrite").partitionBy("ingest_date")
     .parquet(str(output_root / "bronze" / "shipment_events")))

    required_text = ("event_id", "shipment_id", "event_type", "origin_city",
                     "destination_city", "source_system", "carrier")
    valid_expr = F.col("_corrupt_record").isNull()
    for field in required_text:
        valid_expr = valid_expr & F.col(field).isNotNull() & (F.length(F.trim(F.col(field))) > 0)
    valid_expr = (valid_expr & F.col("event_type").isin(
        "CREATED", "DEPARTED_ORIGIN", "ARRIVED_DESTINATION_PORT",
        "CUSTOMS_HOLD", "CUSTOMS_CLEARED", "RECEIVED_WAREHOUSE", "DELIVERED")
        & F.col("event_time").isNotNull()
        & F.col("ingest_time").isNotNull()
        & F.col("planned_delivery_time").isNotNull()
        & F.col("weight_kg").isNotNull()
        & (F.col("weight_kg") > 0))

    invalid = parsed.where(~valid_expr).cache()
    valid = parsed.where(valid_expr).cache()
    invalid_rows = invalid.count()
    valid_rows = valid.count()

    (invalid.withColumn("quality_failure", F.lit("missing_or_invalid_field_or_json"))
     .write.mode("overwrite").json(str(output_root / "quarantine" / "events")))

    # Event IDs are unique logical events. Keep earliest ingested occurrence so
    # rerunning a batch cannot double-count replayed messages.
    by_event_id = Window.partitionBy("event_id").orderBy(
        F.col("ingest_time").asc(), F.col("event_time").asc())
    silver = (valid.withColumn("_rownum", F.row_number().over(by_event_id))
              .where(F.col("_rownum") == 1)
              .drop("_rownum", "_corrupt_record")
              .cache())
    unique_events = silver.count()
    duplicate_rows = valid_rows - unique_events
    (silver.write.mode("overwrite").partitionBy("event_date")
     .parquet(str(output_root / "silver" / "shipment_events")))

    # Shipment status comes from the latest event-time, not arrival order.
    latest_window = Window.partitionBy("shipment_id").orderBy(
        F.col("event_time").desc(), F.col("ingest_time").desc(),
        F.col("event_id").desc())
    latest = (silver.withColumn("_rownum", F.row_number().over(latest_window))
              .where(F.col("_rownum") == 1)
              .select("shipment_id", "carrier", "origin_city", "origin_country",
                      "destination_city", "destination_country", "weight_kg",
                      "planned_delivery_time", F.col("event_type").alias("latest_event_type"),
                      F.col("event_time").alias("latest_event_time")))
    per_shipment = (silver.groupBy("shipment_id")
                    .agg(F.count("event_id").alias("observed_event_count"),
                         F.max(F.when(F.col("event_type") == "DELIVERED", F.col("event_time")))
                          .alias("delivered_time"),
                         F.max(F.when(F.col("event_type") == "CUSTOMS_HOLD", 1)
                               .otherwise(0)).alias("had_customs_hold")))
    gold = (latest.join(per_shipment, "shipment_id", "inner")
            .withColumn("is_late_delivery", F.when(
                F.col("delivered_time").isNotNull(),
                F.col("delivered_time") > F.col("planned_delivery_time"))))
    gold.write.mode("overwrite").parquet(str(output_root / "gold" / "shipment_current"))

    shipment_count = gold.count()
    delivered_count = gold.where(F.col("delivered_time").isNotNull()).count()
    late_count = gold.where(F.col("is_late_delivery") == True).count()
    metrics = {
        "source": str(input_path),
        "input_rows": input_rows,
        "valid_rows": valid_rows,
        "invalid_rows": invalid_rows,
        "duplicate_event_rows": duplicate_rows,
        "silver_unique_event_rows": unique_events,
        "gold_distinct_shipments": shipment_count,
        "delivered_shipments": delivered_count,
        "late_deliveries": late_count,
        "source_type": "synthetic_events",
        "runtime": "local_pyspark",
    }
    # Independent invariants enforce source-to-target reconciliation.
    from logistics.lake_checks import validate_metrics
    validate_metrics(metrics)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "quality_metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    parsed.unpersist()
    valid.unpersist()
    invalid.unpersist()
    silver.unpersist()
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Transform synthetic shipment events into a LOCAL PySpark data lake")
    parser.add_argument("--input", type=Path, default=Path("data/stream/unique_shipment_events.jsonl"))
    parser.add_argument("--output-root", type=Path, default=Path("data/lake"))
    args = parser.parse_args()

    from pyspark.sql import SparkSession
    spark = (SparkSession.builder.appName("global-logistics-local-lake")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.shuffle.partitions", "2")
             .config("spark.ui.enabled", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    try:
        metrics = process(spark, args.input, args.output_root)
    finally:
        spark.stop()
    print(json.dumps(metrics, indent=2))
    print("Parquet data lake built locally; no AWS or cloud APIs used.")


if __name__ == "__main__":
    main()
