# Phase 6 — Self-service dashboard and read-only analytics assistant

## Purpose and scope

This extension adds a local-only Streamlit dashboard over your **existing Phase 4 DuckDB warehouse** and a metrics-grounded question assistant. Your Phase 5 quality monitor remains unchanged. The data is synthetic, **not Amazon data**.

## Windows PowerShell commands

```powershell
cd "C:\Users\uppal\projects\global-logistics"
Expand-Archive -Path "$HOME\Downloads\global-logistics-phase6-files.zip" -DestinationPath . -Force
python -m pip install -r requirements-dashboard.txt
python -m pytest -q
python -m logistics.analytics
python -m logistics.assistant --question "Which carrier has the most late deliveries?"
python -m streamlit run dashboard.py
```

Open `http://127.0.0.1:8501`. Press `Ctrl+C` to exit. The data warehouse must already exist at `data/warehouse/global_logistics.duckdb`; if missing, run `python -m logistics.warehouse build` first.

## What's implemented

- Filterable carrier and route analytics based on **parameterized, read-only** DuckDB queries.
- Shipment totals, delivered shipments, late shipments, customs holds, and on-time percentage. The on-time denominator is *delivered* shipments, not all shipments.
- Carrier and route comparisons, daily event volume, latest status distribution, recorded delay reasons, and 100 most recent/important exception rows.
- Saved Phase 5 quality-gate status shown with a note that the saved report is **not live monitoring**.
- Deterministic analytics assistant with a whitelist of supported questions. It **cannot generate SQL or query unrelated tables**, and answers are backed by visible evidence.
- Optional Ollama mode uses `http://127.0.0.1:11434` only, sends the **already-verified metric answer** to a local model for wording, and never sends information to a hosted model. Ollama is neither installed nor required.
- Streamlit telemetry disabled in `.streamlit/config.toml`. Server bound to the loopback address `127.0.0.1`.

## Optional local generative model

This is **not necessary to complete Phase 6**. The default assistant is an explainable rules-based analytics assistant, **not an LLM**. If you later install free Ollama and download a model such as `llama3.2:1b`, you can enable local LLM commentary. Such commentary can still hallucinate; the verified SQL-derived metrics are the source of truth. Model downloads require disk space/Internet access but no paid API. Do not claim hands-on Bedrock use from this project.

## Quality and safety rules

- Use `python -m logistics.quality_monitor check` before demonstrating dashboard metrics after a data refresh.
- Query filters are bound as parameters; raw question text never reaches SQL.
- Exception list is capped at 100 rows to keep UI responsive. Counts are computed from all selected rows, not just the displayed exceptions.
- `delay_reason` counts unique shipments **per reason**. A shipment can appear under multiple different reasons, so summing them may exceed the number of shipments with delays. The synthetic reason labels do not prove causal impact.
- Filters and assistant evidence use the same warehouse snapshot per dashboard refresh. A rebuild during a query can cause a lock; retry after it finishes.
- No AWS account, credit card, deployment, cloud hosting, or paid AI API is used. Pip installation downloads free open-source packages, and optional Ollama model download can be large.

## Resume-safe description after running the UI

"Built a local, self-service logistics analytics dashboard over DuckDB with read-only parameterized queries, carrier/route KPIs, exception monitoring, and a metrics-grounded question assistant using synthetic shipment data."

If you use and verify optional Ollama, add: "Integrated an optional local LLM to summarize prevalidated operational metrics without generating executable SQL."

Do not list Amazon Bedrock, Redshift, or hosted production AWS work as implemented based on this local project.
