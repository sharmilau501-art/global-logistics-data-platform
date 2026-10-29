-- Global Logistics Phase 4: local DuckDB warehouse.
-- Grain: fact_shipment = one row per shipment; fact_shipment_event = one row per unique event.
-- All inputs are existing Phase 3 Parquet files, not network/cloud services.

CREATE OR REPLACE TABLE dim_carrier AS
SELECT ROW_NUMBER() OVER (ORDER BY carrier) AS carrier_key, carrier
FROM (SELECT DISTINCT carrier FROM stg_shipment_current);

CREATE OR REPLACE TABLE dim_route AS
SELECT
    ROW_NUMBER() OVER (ORDER BY origin_country, origin_city, destination_country, destination_city) AS route_key,
    origin_city, origin_country, destination_city, destination_country
FROM (
    SELECT DISTINCT origin_city, origin_country, destination_city, destination_country
    FROM stg_shipment_current
);

CREATE OR REPLACE TABLE dim_date AS
WITH dates AS (
    SELECT CAST(event_time AS DATE) AS date_value FROM stg_events
    UNION
    SELECT CAST(planned_delivery_time AS DATE) FROM stg_shipment_current
    UNION
    SELECT CAST(delivered_time AS DATE) FROM stg_shipment_current
    WHERE delivered_time IS NOT NULL
    UNION
    SELECT CAST(latest_event_time AS DATE) FROM stg_shipment_current
)
SELECT
    CAST(STRFTIME(date_value, '%Y%m%d') AS INTEGER) AS date_key,
    date_value,
    YEAR(date_value) AS year_number,
    MONTH(date_value) AS month_number,
    DAY(date_value) AS day_number,
    DAYNAME(date_value) AS weekday_name
FROM dates
WHERE date_value IS NOT NULL;

CREATE OR REPLACE TABLE fact_shipment AS
SELECT
    g.shipment_id,
    c.carrier_key,
    r.route_key,
    CAST(STRFTIME(CAST(g.planned_delivery_time AS DATE), '%Y%m%d') AS INTEGER) AS planned_delivery_date_key,
    g.weight_kg,
    g.planned_delivery_time,
    g.delivered_time,
    g.latest_event_type,
    g.latest_event_time,
    g.observed_event_count,
    CAST(g.had_customs_hold AS BOOLEAN) AS had_customs_hold,
    (g.delivered_time IS NOT NULL) AS is_delivered,
    CAST(g.is_late_delivery AS BOOLEAN) AS is_late_delivery
FROM stg_shipment_current AS g
JOIN dim_carrier AS c ON g.carrier = c.carrier
JOIN dim_route AS r
    ON g.origin_city = r.origin_city
   AND g.origin_country = r.origin_country
   AND g.destination_city = r.destination_city
   AND g.destination_country = r.destination_country;

CREATE OR REPLACE TABLE fact_shipment_event AS
SELECT
    e.event_id,
    e.shipment_id,
    CAST(STRFTIME(CAST(e.event_time AS DATE), '%Y%m%d') AS INTEGER) AS event_date_key,
    e.event_type,
    e.event_time,
    e.ingest_time,
    e.delay_reason,
    e.source_system
FROM stg_events AS e;

CREATE OR REPLACE TABLE mart_carrier_performance AS
WITH stats AS (
    SELECT
        c.carrier,
        COUNT(*) AS total_shipments,
        COUNT(*) FILTER (WHERE f.is_delivered) AS delivered_shipments,
        COUNT(*) FILTER (WHERE f.is_late_delivery) AS late_deliveries,
        COUNT(*) FILTER (WHERE f.had_customs_hold) AS customs_hold_shipments
    FROM fact_shipment f
    JOIN dim_carrier c ON f.carrier_key = c.carrier_key
    GROUP BY c.carrier
)
SELECT
    *,
    ROUND(100.0 * (delivered_shipments - late_deliveries)
        / NULLIF(delivered_shipments, 0), 2) AS on_time_delivery_pct
FROM stats;

CREATE OR REPLACE TABLE mart_route_performance AS
WITH stats AS (
    SELECT
        r.origin_city,
        r.origin_country,
        r.destination_city,
        r.destination_country,
        COUNT(*) AS total_shipments,
        COUNT(*) FILTER (WHERE f.is_delivered) AS delivered_shipments,
        COUNT(*) FILTER (WHERE f.is_late_delivery) AS late_deliveries,
        COUNT(*) FILTER (WHERE f.had_customs_hold) AS customs_hold_shipments
    FROM fact_shipment f
    JOIN dim_route r ON f.route_key = r.route_key
    GROUP BY r.origin_city, r.origin_country, r.destination_city, r.destination_country
)
SELECT
    *,
    ROUND(100.0 * (delivered_shipments - late_deliveries)
        / NULLIF(delivered_shipments, 0), 2) AS on_time_delivery_pct
FROM stats;

CREATE OR REPLACE TABLE mart_daily_event_volume AS
SELECT
    CAST(event_time AS DATE) AS event_date,
    event_type,
    COUNT(*) AS event_count
FROM fact_shipment_event
GROUP BY CAST(event_time AS DATE), event_type;
