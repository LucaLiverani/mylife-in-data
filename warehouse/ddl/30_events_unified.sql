-- Phase 3 — silver.events_unified. The shared seam where every source's
-- event projections land in a common shape, feeding the cross-source
-- /api/home/recent-events and /api/overview/stats handlers.

CREATE TABLE IF NOT EXISTS silver.events_unified (
    event_ts          DateTime64(3),
    source            LowCardinality(String),  -- 'spotify','youtube','maps','calendar'
    kind              LowCardinality(String),  -- 'play','liked','watch','place_visit','meeting', …
    title             String,
    subtitle          String,
    image_url         String,
    is_from_ads       UInt8 DEFAULT 0,
    metadata          String,                  -- JSON catch-all
    event_id          UUID
) ENGINE = MergeTree
ORDER BY (event_ts, source, event_id);
