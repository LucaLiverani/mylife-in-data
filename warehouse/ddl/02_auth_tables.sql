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
