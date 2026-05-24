-- Phase 6 — YouTube history (Data Portability) + metadata catalog (Data API v3).

CREATE TABLE IF NOT EXISTS bronze.youtube_watch_history (
    watched_at         DateTime64(3),
    video_id           String,
    video_title        String,
    video_url          String,
    channel_id         String,
    channel_title      String,
    activity_type      LowCardinality(String),
    is_from_ads        Bool,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (video_id, watched_at);

CREATE TABLE IF NOT EXISTS bronze.youtube_search_history (
    searched_at        DateTime64(3),
    query              String,
    _ingested_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_ingested_at)
ORDER BY (searched_at, query);

CREATE TABLE IF NOT EXISTS bronze.youtube_videos (
    video_id           String,
    video_title        String,
    channel_id         String,
    category_id        String,
    duration_seconds   Int32,
    published_at       DateTime,
    default_language   LowCardinality(String),
    _fetched_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY video_id;

CREATE TABLE IF NOT EXISTS bronze.youtube_channels (
    channel_id              String,
    channel_title           String,
    primary_category_name   LowCardinality(String),
    subscriber_count        Int32,
    thumbnail_url           String,
    _fetched_at             DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_fetched_at)
ORDER BY channel_id;
