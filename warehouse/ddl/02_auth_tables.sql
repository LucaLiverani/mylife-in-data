-- Phase 0 — auth tables. Google token storage + alert log.
-- Google tokens land here on first OAuth handshake (Phase 4). The dashboard's
-- Pages Function and the Dagster GoogleAuthResource both upsert into this
-- table; the ReplacingMergeTree's _updated_at column resolves concurrent writes.

CREATE TABLE IF NOT EXISTS auth.google_tokens (
    account_email     String,
    refresh_token     String,
    access_token      String,
    expires_at        DateTime,
    scopes            Array(String),
    issued_at         DateTime,
    _updated_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_updated_at)
ORDER BY account_email;

-- Operator-visible alerts: token expiry, auth failures, freshness misses, etc.
CREATE TABLE IF NOT EXISTS auth.alerts (
    raised_at         DateTime DEFAULT now(),
    kind              LowCardinality(String),
    account_email     String,
    message           String
) ENGINE = MergeTree
ORDER BY (raised_at);

-- Calendar push channels — one row per (calendar_id, channel_id). Phase 7
-- writes here on events.watch setup; the sync sensor uses sync_token to
-- resume from the last delta.
CREATE TABLE IF NOT EXISTS auth.calendar_channels (
    calendar_id        String,
    calendar_name      String,
    channel_id         String,                -- our UUID, passed to events.watch
    resource_id        String,                -- Google's resource ID
    sync_token         String DEFAULT '',     -- nextSyncToken from latest events.list
    expiration         DateTime,              -- when Google says it'll stop pushing
    started_at         DateTime DEFAULT now(),
    _updated_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(_updated_at)
ORDER BY (calendar_id, channel_id);
