-- Maps trip pipeline — home anchor, segmented trips, LLM enrichment, weather.
-- (The legacy Timeline bronze tables that used to live here, maps_visits /
-- maps_path / maps_search / maps_directions, were removed: Timeline moved
-- on-device in 2024 and full history now comes from Google Takeout. The
-- primary daily Maps flow is bronze.maps_activity in 51_maps_activity.sql.)

-- Home anchor — drives trip segmentation. One active row at any point;
-- multi-row history if the user moves (valid_from gives the piecewise lookup).
CREATE TABLE IF NOT EXISTS silver.maps_home_locations (
    valid_from   Date,
    lat          Float64,
    lng          Float64,
    radius_km    Float32,
    label        String,
    _set_at      DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_set_at)
ORDER BY valid_from;

-- One row per detected trip; populated by the Dagster `maps_trip_segmentation`
-- asset after each maps ingest. TRUNCATE+INSERT rebuild is fine — the table
-- stays tiny at personal-history scale.
CREATE TABLE IF NOT EXISTS silver.maps_trips (
    started_at           Date,
    ended_at             Date,
    days                 Int16,
    destination          String,
    destination_country  String,
    km                   Int32,
    localities           Int16 DEFAULT 0,    -- distinct localities visited on the trip
    countries            Int16 DEFAULT 0,    -- distinct countries on the trip
    max_km               Int32 DEFAULT 0     -- farthest point from home (km)
) ENGINE = MergeTree
ORDER BY started_at;

-- Idempotent migration for the activity-derived segmentation (Phase 4).
ALTER TABLE silver.maps_trips ADD COLUMN IF NOT EXISTS localities Int16 DEFAULT 0;
ALTER TABLE silver.maps_trips ADD COLUMN IF NOT EXISTS countries  Int16 DEFAULT 0;
ALTER TABLE silver.maps_trips ADD COLUMN IF NOT EXISTS max_km     Int32 DEFAULT 0;

-- Phase 5 — LLM adjudication of inferred trips. The geometric segmenter emits
-- trip CANDIDATES; the `maps_trip_llm` asset gathers each window's Maps + Calendar
-- evidence and asks an LLM to decide if it's a genuine trip, classify it, pick a
-- de-noised destination, and write a title + summary. Keyed by `trip_key`
-- ('<start>_<end>') so re-segmentation that shifts a boundary simply re-enriches
-- the new window (and the old row ages out — ReplacingMergeTree, read with FINAL).
CREATE TABLE IF NOT EXISTS silver.maps_trips_enriched (
    trip_key             String,                            -- '<started_at>_<ended_at>'
    started_at           Date,
    ended_at             Date,
    days                 Int16,
    is_trip              UInt8,                             -- LLM verdict: genuine trip vs noise/layover
    confidence           Float32,                           -- 0..1
    trip_type            LowCardinality(String),            -- leisure|business|weekend|day_trip|relocation|visiting|other
    title                String,                            -- short human title ("Long weekend in Berlin")
    destination_label    String,                            -- de-noised primary destination (city / region)
    destination_country  String,
    summary              String,                            -- 1-2 sentence narrative
    evidence             String,                            -- short free-text rationale from the model
    suggested_split      String DEFAULT '',                 -- JSON array of {start,end,label} when a mega-trip splits, else ''
    model                LowCardinality(String) DEFAULT '', -- LLM_MODEL that produced this row
    _enriched_at         DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_enriched_at)
ORDER BY trip_key;

-- User confirm / reject / edit loop over the LLM verdicts. Empty by default;
-- the dashboard writes rows here (Phase 6/7). Downstream gold can LEFT JOIN on
-- trip_key to let a human override the model. ReplacingMergeTree keeps the
-- latest action per trip.
CREATE TABLE IF NOT EXISTS silver.maps_trip_labels (
    trip_key             String,
    label                LowCardinality(String),            -- 'confirm' | 'reject' | 'edit'
    edited_title         String DEFAULT '',
    edited_destination   String DEFAULT '',
    edited_trip_type     String DEFAULT '',
    note                 String DEFAULT '',
    _set_at              DateTime64(3) DEFAULT now64()
) ENGINE = ReplacingMergeTree(_set_at)
ORDER BY trip_key;

-- Phase 6 — historical weather per trip from Open-Meteo (free archive API, no
-- key). Filled by the `maps_trip_weather` asset for the trip's destination
-- (dominant-locality coords) over its date window. Monotonic per trip_key
-- (only un-weathered trips are fetched); recent trips inside the archive's
-- ~5-day lag get filled on a later run. gold_maps_trips LEFT JOINs this.
CREATE TABLE IF NOT EXISTS silver.maps_trip_weather (
    trip_key             String,
    lat                  Float64,
    lng                  Float64,
    temp_mean            Float32,    -- °C, mean of daily means over the window
    temp_max             Float32,    -- °C, mean of daily highs
    temp_min             Float32,    -- °C, mean of daily lows
    precip_mm            Float32,    -- total precipitation over the window
    summary              String,     -- short human label ("18°C avg · 12mm rain")
    _fetched_at          DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY trip_key;
