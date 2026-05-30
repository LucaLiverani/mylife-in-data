-- Phase 5b — Maps activity-based pipeline.
--
-- Google's Data Portability API gives us `myactivity.maps` (search/view/
-- directions, ~4-5MB/day) and `maps.starred_places` (saved places) but NOT
-- Timeline / location history (which moved on-device in 2024). So:
--
--   1. bronze.maps_activity   ← MyActivity entries (replaces visits/paths
--                                as the primary daily source)
--   2. bronze.maps_place_catalog ← cached Places API + Geocoding lookups
--                                  (place_id → name, type, neighborhood)
--   3. silver.maps_private_places ← coordinates ONLY from starred places,
--                                   used as a spatial filter so friends'
--                                   addresses never reach gold tables
--
-- The Timeline tables (bronze.maps_visits, bronze.maps_path) defined in
-- 50_maps.sql remain, fed only by monthly manual export via
-- scripts/import_maps_timeline_export.py.

CREATE TABLE IF NOT EXISTS bronze.maps_activity (
    event_ts          DateTime64(3),
    activity_type     LowCardinality(String),       -- 'search' | 'view_place' | 'directions' | 'other'
    query             String,                       -- search query (empty if not a search)
    place_name        String,                       -- resolved place name (from MyActivity title)
    place_id          String,                       -- Google ftid extracted from URL (may differ from Places API id)
    lat               Float64,
    lng               Float64,
    origin            String,                       -- directions: "from X"
    destination       String,                       -- directions: "to Y"
    raw_url           String,                       -- titleUrl, for debugging and re-parsing
    _ingested_at      DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (event_ts, place_id);

-- Looked up lazily by the place-enrichment sensor; each place looked up
-- exactly once. Catalog grows monotonically.
CREATE TABLE IF NOT EXISTS bronze.maps_place_catalog (
    place_id          String,                       -- our internal key (ftid from MyActivity URL OR Places API place_id)
    lookup_key        String,                       -- what we queried Places API with (text or coords)
    place_name        String,
    place_types       Array(LowCardinality(String)),
    primary_type      LowCardinality(String),       -- first non-generic from place_types
    lat               Float64,
    lng               Float64,
    formatted_address String,
    neighborhood      String,                       -- 'Kreis 6', 'Mission District', etc.
    sublocality       String,                       -- finer-grained when available
    locality          String,                       -- city
    admin_area_1      String,                       -- state/region
    country           String,
    country_code      LowCardinality(String),       -- ISO 3166-1 alpha-2
    match_confidence  Float32 DEFAULT 0,             -- geocoder score 0..1 (gates the map)
    match_type        LowCardinality(String) DEFAULT '',  -- result granularity, or 'unresolved' sentinel
    _fetched_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY place_id;

-- Backfill the enrichment-quality columns onto a pre-existing catalog (no-op on
-- a fresh table — the CREATE above already includes them).
ALTER TABLE bronze.maps_place_catalog ADD COLUMN IF NOT EXISTS match_confidence Float32 DEFAULT 0;
ALTER TABLE bronze.maps_place_catalog ADD COLUMN IF NOT EXISTS match_type LowCardinality(String) DEFAULT '';

-- Private filter — coordinates ONLY. NEVER stores place_name (it'd be a
-- friend's address with their name attached). 100m radius is a city-block
-- match; tunable per row.
CREATE TABLE IF NOT EXISTS silver.maps_private_places (
    lat               Float64,
    lng               Float64,
    radius_m          Int32 DEFAULT 100,
    _set_at           DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_set_at)
ORDER BY (lat, lng);

-- ── Enrichment join key ─────────────────────────────────────────────────────
-- Single source of truth for how an activity row maps to a catalog entry.
--   best_text — the most specific free text on the row (place name / search
--                query / directions destination); the input handed to the
--                Places / Geocoding lookup.
--   geo_key   — the catalog key: the URL ftid when present, otherwise a
--                normalized-text key `q:<lowercased, whitespace-collapsed>`.
--                Most MyActivity URLs carry NO ftid, so the text key is what
--                lets searches / directions / place views enrich at all.
-- The enrichment worklist (orchestration/.../google.py) and the silver join
-- (silver_maps_activity_enriched) both read these columns from HERE, so the
-- lookup key and the join key can never drift apart.
CREATE OR REPLACE VIEW silver.maps_activity_keyed AS
WITH base AS (
    SELECT
        *,
        multiIf(
            place_name != '',                                    place_name,
            activity_type = 'search'     AND query != '',        query,
            activity_type = 'directions' AND destination != '',  destination,
            query != '',                                         query,
            destination != '',                                   destination,
            ''
        ) AS best_text
    FROM bronze.maps_activity FINAL
)
SELECT
    *,
    if(
        place_id != '',
        place_id,
        if(
            best_text != '',
            concat('q:', trimBoth(replaceRegexpAll(lowerUTF8(best_text), '[[:space:]]+', ' '))),
            ''
        )
    ) AS geo_key
FROM base;
