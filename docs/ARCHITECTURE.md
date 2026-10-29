# Global Logistics Local-Only Architecture

This repository is a $0-cloud-charge learning project. It is NOT a deployed AWS implementation.

| AWS concept | Actual local technology (planned) |
|---|---|
| Kinesis streaming | Apache Kafka Docker container |
| Lambda event processing | Local Python consumer |
| S3 data lake | Local directories, optionally MinIO |
| AWS Glue transformations | Local PySpark |
| Amazon Redshift warehouse | DuckDB |
| CloudWatch | Structured logs, local metrics |
| AWS Bedrock | Optional local rule-based explanations or local model |
| CI/CD | GitHub Actions public-repo free-tier limits, or local tests |

Phase 1 is implemented: deterministic event simulator, JSONL raw zone, quality inspection, unit tests.
Phase 2 onward is planned, not implemented.

No credentials or paid resources are needed. Do not add an AWS access key or AWS SDK calls.
