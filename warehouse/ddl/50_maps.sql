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
    km                   Int32
) ENGINE = MergeTree
ORDER BY started_at;
