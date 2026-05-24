-- Phase 7 — Google Calendar push pipeline.

CREATE TABLE IF NOT EXISTS bronze.calendar_events (
    event_id           String,
    calendar_id        String,
    calendar_name      String,
    started_at         DateTime64(3),
    ended_at           DateTime64(3),
    title              String,
    description        String,
    location           String,
    status             LowCardinality(String),
    attendee_count     Int16,
    recurrence_id      String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (event_id, started_at);

CREATE TABLE IF NOT EXISTS bronze.calendar_sync_notifications (
    received_at        DateTime64(3) DEFAULT now64(),
    channel_id         String,
    resource_id        String,
    calendar_id        String,
    message_number     UInt64,
    processed_at       Nullable(DateTime64(3)),
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (channel_id, message_number);

-- Optional alias table for prettier category names. Empty by default —
-- silver_calendar_events falls back to calendar_name.
CREATE TABLE IF NOT EXISTS silver.calendar_category_aliases (
    calendar_name       String,
    display_category    String,
    _set_at             DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_set_at)
ORDER BY calendar_name;
