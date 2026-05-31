-- Phase 5 — Maps via Google Data Portability API.

CREATE TABLE IF NOT EXISTS bronze.maps_visits (
    started_at         DateTime64(3),
    ended_at           DateTime64(3),
    place_name         String,
    place_id           String,                 -- Google Places ID when present
    place_address      String,                 -- "City, Country" usually
    lat                Float64,
    lng                Float64,
    confidence         Float32,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (started_at, place_id);

CREATE TABLE IF NOT EXISTS bronze.maps_path (
    started_at         DateTime64(3),
    ended_at           DateTime64(3),
    start_lat          Float64,
    start_lng          Float64,
    end_lat            Float64,
    end_lng            Float64,
    distance_m         Int32,
    activity_type      LowCardinality(String),
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (started_at);

CREATE TABLE IF NOT EXISTS bronze.maps_search (
    searched_at        DateTime64(3),
    query              String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (searched_at);

CREATE TABLE IF NOT EXISTS bronze.maps_directions (
    requested_at       DateTime64(3),
    origin             String,
    destination        String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (requested_at);

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
