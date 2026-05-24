# Implementation Plan

This document drives an auto-mode execution of all pipelines in `DATA_MODEL.md` and `PIPELINES.md`. Read **§1 Pre-flight** end-to-end and complete every checkbox before running `claude --auto`; the plan assumes the listed credentials/env values are in place. Read **§2 Auth strategy** to understand the weekly re-auth dance for Google sources — that's the one unavoidable manual step in steady-state operation.

---

## 1. Pre-flight checklist — actions only you can do

> 🛑 **Do these in order. Auto-mode cannot proceed past Phase 4 without §1.2 and §1.4 done.**

### 1.1 — Spotify scope upgrade (5 min)

Existing app dashboard at <https://developer.spotify.com/dashboard>. No new app needed. **You will need to re-run `authenticate_local.py` once the script's scope list is updated by Phase 2** — auto-mode does the script edit; you do the browser re-auth.

The new scopes added are:
- `user-library-read` — for the saved-tracks ("Liked") producer
- (existing) `user-read-recently-played`, `user-read-playback-state`, `user-read-currently-playing`, `user-read-private`

### 1.2 — Google Cloud Console (30 min, one-time)

1. **Project**: <https://console.cloud.google.com> → create a project named `mylife-in-data` (or pick an existing one).
2. **Enable APIs** (APIs & Services → Library):
   - [ ] **Google Calendar API**
   - [ ] **YouTube Data API v3**
   - [ ] **Data Portability API**
3. **OAuth consent screen** (APIs & Services → OAuth consent screen):
   - User type: **External**
   - App name: `Mylife Personal Pipeline`
   - User support email / Developer contact: your email
   - **Add scopes** (Manage scopes → Add or remove scopes):
     - `https://www.googleapis.com/auth/calendar.events.readonly`
     - `https://www.googleapis.com/auth/calendar.readonly`
     - `https://www.googleapis.com/auth/youtube.readonly`
     - `https://www.googleapis.com/auth/dataportability.youtube.watch_history`
     - `https://www.googleapis.com/auth/dataportability.youtube.search_history`
     - `https://www.googleapis.com/auth/dataportability.maps.aliased_places`
     - `https://www.googleapis.com/auth/dataportability.maps.starred_places`
     - (any other dataportability scope that's relevant — verify available list via the [Data Portability scopes page](https://developers.google.com/data-portability/user-guide/scopes))
   - **Test users**: add your own email
   - **Save**; leave **Publishing status: Testing**
4. **OAuth client ID** (APIs & Services → Credentials → Create credentials → OAuth client ID):
   - Application type: **Web application** (NOT Desktop — we need to declare the Pages-Function callback as a valid redirect URI)
   - Authorized redirect URIs:
     - `http://127.0.0.1:8000/callback` (one-time local auth on laptop)
     - `https://<PAGES_DOMAIN>/api/_internal/google-auth-callback` (re-auth from anywhere)
   - Note the **Client ID** and **Client Secret**
5. **Drop into `infrastructure/.env`** (auto-mode will pre-create the empty keys in §0 scaffolding):
   ```
   GOOGLE_CLIENT_ID=
   GOOGLE_CLIENT_SECRET=
   GOOGLE_REDIRECT_URI=https://<PAGES_DOMAIN>/api/_internal/google-auth-callback
   ```

> ⚠️ **Maps Timeline probe**: After OAuth is wired (Phase 5), run `scripts/probe_maps_data_portability.py`. If it returns no recent visits, your Maps history is now on-device only (post-2024 migration) — you'll need to fall back to manual on-device Timeline exports for Maps. The probe takes 5 minutes; better to know up-front.

### 1.3 — Cloudflare R2 bucket (10 min, one-time)

1. Cloudflare dashboard → R2 → **Create bucket** → name `mylife-raw` (or anything; just put it in env)
2. R2 → Manage R2 API Tokens → **Create API token** → name `dagster-r2`, permission **Object Read & Write**, specific bucket `mylife-raw`
3. Note: **Account ID**, **Access Key ID**, **Secret Access Key**, **S3-compatible endpoint URL**
4. Drop into `infrastructure/.env`:
   ```
   R2_ACCOUNT_ID=...
   R2_ACCESS_KEY_ID=...
   R2_SECRET_ACCESS_KEY=...
   R2_BUCKET=mylife-raw
   R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com
   ```

### 1.4 — Cloudflare Pages webhook secrets (5 min)

The Pages project hosts two new internal endpoints (calendar webhook + Google re-auth callback). Both need secrets.

1. Generate two secrets locally:
   ```bash
   openssl rand -hex 32  # CALENDAR_WEBHOOK_TOKEN
   openssl rand -hex 32  # GOOGLE_REAUTH_STATE_SECRET
   ```
2. Add both to `dashboard/.env.production` (auto-mode appends them to the deploy script's secrets-upload step):
   ```
   CALENDAR_WEBHOOK_TOKEN=...
   GOOGLE_REAUTH_STATE_SECRET=...
   ```
3. Same values into `infrastructure/.env` (used by Dagster):
   ```
   CALENDAR_WEBHOOK_TOKEN=...
   GOOGLE_REAUTH_STATE_SECRET=...
   ```
4. Re-deploy Pages once at the end of Phase 7: `cd dashboard && ./scripts/deploy-to-pages.sh`. Auto-mode will surface this step.

### 1.5 — DNS for the Google re-auth UI

The Google OAuth client ID expects a public HTTPS callback URL. The existing Pages project already serves at `https://<PAGES_DOMAIN>`. No new DNS work needed — just confirm `https://<PAGES_DOMAIN>/api/_internal/google-auth-callback` resolves to the Pages deployment after Phase 4 ships.

---

## 2. Auth strategy

### Spotify — easy

- access_token TTL: 1 hour, refreshed automatically by spotipy
- refresh_token: **does not expire** under normal conditions (revoked only on Spotify password change or app-permission revoke)
- Storage: `tokens/.spotify_cache` file (gitignored, bind-mounted into Dagster)
- Dagster `SpotifyResource` wraps spotipy's `CacheFileHandler`; refresh is transparent
- Re-auth needed: only on Spotify password change or revoke

### Google — the 7-day rule

> **Verified from Google's OAuth docs**: An external-user-type app in **Testing** publishing status with any scope beyond `userinfo.email/profile/openid` gets refresh tokens that **expire after 7 days**. To get long-lived refresh tokens, the app needs to be in **Production** with OAuth verification — restricted scopes (Data Portability counts) additionally require a security assessment, ~4-6 weeks turnaround.

For a personal data project on personal Gmail, we accept the 7-day reality and build a **weekly re-auth dance**:

```
┌─ Every Monday ────────────────────────────────────────────────┐
│ Dagster `google_token_health` schedule checks token age       │
│   → if refresh_token issued > 6 days ago: send notification   │
│                                                                │
│ User clicks the re-auth link from the notification             │
│   → opens browser to /api/_internal/google-auth-redirect       │
│   → redirects to Google consent screen                         │
│   → Google redirects back to /api/_internal/google-auth-callback│
│   → Pages Function exchanges code for tokens                   │
│   → writes new {refresh_token, access_token, expires_at} into │
│     auth.google_tokens in ClickHouse (via tunnel + service     │
│     token)                                                     │
│                                                                │
│ Dagster `GoogleAuthResource` reads from auth.google_tokens     │
│ on every resource init — always picks up the fresh token       │
└────────────────────────────────────────────────────────────────┘
```

**Key design choices**:
- Tokens live in **ClickHouse** (`auth.google_tokens`), not on disk. The Pages Function can write there over the existing tunnel; Dagster reads from there. No filesystem coordination needed.
- access_token (1h TTL) is refreshed in-process by `google-auth` library using the stored refresh_token; the refreshed access_token is written back to ClickHouse so other Dagster runs see it.
- refresh_token rotation: Google sometimes issues a new refresh_token on refresh — `GoogleAuthResource` writes whichever it gets back.
- Notification mechanism: starts as a Dagster UI alert. Adding email notification via Cloudflare Email Service is a Phase 8 stretch goal.

**Long-term escape hatch** (Phase 9, post-launch):
- Apply for Google OAuth verification (privacy policy + app homepage required, both can live on the dashboard's Pages site)
- For restricted scopes (Data Portability), follow the security-assessment process
- Once verified → drop the 7-day dance, refresh tokens are effectively permanent

### Google Calendar push channels — automatic renewal

Separate concern from user-token refresh. `events.watch` channels have a max TTL (Google doesn't publish the exact value; treat as 7 days conservatively). Dagster `calendar_channels_renew` schedule runs daily, re-watches each calendar with a new channel ID before expiry. Old channels are left to expire naturally; new ones take over on the next event.

### YouTube Data API v3 quota

- Default: 10,000 quota units/day
- `videos.list(id=<batch of 50>, part=snippet,contentDetails)` = 1 quota unit
- `channels.list(id=<batch>, part=snippet)` = 1 quota unit
- Personal usage: <500 unique video_ids/day → 10 calls/day, ~10 units. Plenty of headroom.
- If we ever hit quota, the enricher sensor logs and tries again next day; no pipeline failure.

---

## 3. Phase execution

Each phase has: **Goal**, **Depends on**, **Build**, **Verify**. Auto-mode should commit after each phase succeeds (`git commit -m "phase N: <goal>"`).

### Phase 0 — Scaffolding

**Goal**: project structure ready for all subsequent phases; no behaviour change yet.

**Depends on**: §1.3 R2 bucket created and env populated.

**Build**:
- `ingestion/_shared/__init__.py`
- `ingestion/_shared/clickhouse.py` — `get_client()` returns `clickhouse_connect` Client from env; `execute(sql)`, `insert_rows(table, rows)` helpers with retry
- `ingestion/_shared/redpanda.py` — `get_producer()` wraps `KafkaProducer(bootstrap_servers='redpanda:9092', value_serializer=json.dumps, …)`
- `ingestion/_shared/r2.py` — `get_client()` returns boto3 S3 client configured for R2 (`endpoint_url=R2_ENDPOINT`, `aws_access_key_id=R2_ACCESS_KEY_ID`, …); `upload_bytes(key, data)`, `download_bytes(key)` helpers
- `ingestion/_shared/json_utils.py` — `dumps` with datetime coercion, `loads` with ms→datetime coercion
- `orchestration/dagster/resources.py` skeleton with:
  - `class ClickHouseResource(ConfigurableResource)` — wraps `_shared/clickhouse.get_client`
  - `class RedpandaResource(ConfigurableResource)` — wraps `_shared/redpanda.get_producer`
  - `class R2Resource(ConfigurableResource)` — wraps `_shared/r2.get_client`
  - Empty stubs for `SpotifyResource`, `GoogleAuthResource` (filled in later phases)
- `orchestration/dagster/assets/__init__.py` — empty package
- `orchestration/dagster/definitions.py` — load resources + assets/__init__.py module-discovered list
- `transformations/dbt_project.yml` — `name: mylife`, `profile: mylife`, `target-path: target`, source paths under `models/`
- `transformations/profiles.yml.example` — ClickHouse profile template (host, port, user, password, schema=default, secure=False, driver=native); auto-mode generates `profiles.yml` from env on first dbt run
- `transformations/models/sources.yml` — declare `bronze.*` tables as dbt sources for ref()-tracking
- `transformations/models/silver/.gitkeep`, `models/gold/.gitkeep`
- `transformations/.gitignore` — `target/`, `dbt_packages/`, `profiles.yml`, `logs/`
- `transformations/packages.yml` — empty for now (no external dbt packages)
- `warehouse/ddl/01_databases.sql`:
  ```sql
  CREATE DATABASE IF NOT EXISTS bronze;
  CREATE DATABASE IF NOT EXISTS silver;
  CREATE DATABASE IF NOT EXISTS gold;
  CREATE DATABASE IF NOT EXISTS auth;
  ```
- `warehouse/ddl/02_auth_tables.sql`:
  ```sql
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

  CREATE TABLE IF NOT EXISTS auth.alerts (
      raised_at         DateTime DEFAULT now(),
      kind              LowCardinality(String),  -- 'token_expiring', 'auth_failed', etc.
      account_email     String,
      message           String
  ) ENGINE = MergeTree
  ORDER BY (raised_at);
  ```
- `warehouse/ddl/apply.sh` — small bash that runs every `*.sql` against the ClickHouse HTTP endpoint, idempotent
- `scripts/init_warehouse.py` — Python wrapper around `apply.sh` so it's runnable from Dagster as an asset too
- Compose changes: `infrastructure/compose/dagster/docker-compose.yml` — bind-mount `./tokens:/opt/dagster/tokens:ro` and `./transformations:/opt/dagster/transformations:ro`; add R2_* and GOOGLE_*/CALENDAR_* env passthrough
- Env files: append the new keys to `infrastructure/.env` (blank) and `.env.example` (placeholder), per the env-file-handling memory
- `infrastructure/start-all.sh` — append a step after ClickHouse healthcheck: `bash warehouse/ddl/apply.sh`

**Verify**:
- `./infrastructure/start-all.sh` runs clean
- `docker exec clickhouse clickhouse-client --query 'SHOW DATABASES'` returns `auth, bronze, default, gold, silver, system`
- `docker exec dagster-webserver python -c "from orchestration.dagster.definitions import defs; print(defs)"` succeeds
- `cd transformations && dbt debug` (run inside Dagster container) returns "All checks passed"

---

### Phase 1 — Spotify current track end-to-end

**Goal**: live `gold.gold_spotify_current_track` row, dashboard tile shows real data, `_meta.cached: false`.

**Depends on**: Phase 0; existing `tokens/.spotify_cache` (already done in this session).

**Build**:
- `warehouse/ddl/10_spotify_current_track.sql`:
  - `bronze.kafka_spotify_player_current` — Kafka engine, topic `spotify.player.current`, JSONEachRow
  - `bronze.spotify_player_current` — storage table (schema per DATA_MODEL.md)
  - `bronze.mv_spotify_player_current` — MV pumping Kafka → storage table
- `transformations/models/sources.yml` — add `bronze.spotify_player_current` as a source
- `transformations/models/gold/gold_spotify_current_track.sql` — dbt model materialized as `view`, exactly the SELECT in DATA_MODEL.md `/api/spotify/current` section
- `ingestion/spotify/producer_current.py` — long-running while-True loop:
  - Reads from `SpotifyResource` (loads cache from `/opt/dagster/tokens/.spotify_cache`)
  - Calls `me/player/currently-playing` every 5s
  - On track change or `is_playing` flip, publishes one JSON message to topic `spotify.player.current` via `RedpandaResource`
  - Includes graceful 429 backoff (`Retry-After` header) and 401 → token-refresh-retry
  - SIGTERM-safe (flush producer, exit 0)
- `orchestration/dagster/resources.py` — fill in `SpotifyResource`:
  - Scopes: `user-read-currently-playing user-read-playback-state user-read-recently-played user-read-private` (Liked scope added in Phase 2)
  - Cache path: `/opt/dagster/tokens/.spotify_cache`
  - Returns a memoized `spotipy.Spotify` client
- `infrastructure/compose/dagster/docker-compose.yml` — add a 4th service:
  - `spotify-current-producer`: same image as `dagster-webserver`, command `python ingestion/spotify/producer_current.py`, env passthrough, `restart: unless-stopped`, mounts `tokens:/opt/dagster/tokens:ro`
- `orchestration/dagster/assets/spotify.py` — add `spotify_current_track_schema` asset that runs `warehouse/ddl/10_spotify_current_track.sql` idempotently (for parity with future schemas)

**Verify**:
- `scripts/verify_phase_1.py`:
  - SELECT count(*) FROM bronze.spotify_player_current — > 0 after 30s of running
  - SELECT * FROM gold.gold_spotify_current_track — returns a row, columns match `dashboard/functions/api/spotify/current.ts:12-35`
  - curl `https://<PAGES_DOMAIN>/api/spotify/current` → `_meta.cached: false`
  - `docker ps | grep spotify-current-producer` → Up

---

### Phase 2 — Spotify history + catalogs + Liked

**Goal**: `gold.gold_spotify_*` set populated; `/api/spotify/{summary,data,recent}` flip off the cached flag; "Liked" events appearing in bronze.

**Depends on**: Phase 1; **§1.1 USER ACTION**: re-run `authenticate_local.py` after Phase 2 updates the scope list to include `user-library-read`.

**Build**:
- `warehouse/ddl/20_spotify_history.sql` — bronze tables: `spotify_plays_raw`, `spotify_tracks`, `spotify_artists`, `spotify_saved_tracks` (schemas per DATA_MODEL.md)
- `ingestion/spotify/recently_played.py` — Dagster asset logic:
  - `me/player/recently-played?limit=50` → JSON
  - INSERT into `bronze.spotify_plays_raw` (ReplacingMergeTree dedupes)
  - Stage same JSON to R2 at `r2://mylife-raw/spotify/plays/<YYYY-MM-DD>/<run_id>.json` for replay
- `ingestion/spotify/saved_tracks.py` — same pattern, `me/tracks?limit=50` paginated, INSERT into `bronze.spotify_saved_tracks`
- `ingestion/spotify/enrichment.py` — runs every ~10 min:
  - `SELECT DISTINCT track_id FROM bronze.spotify_plays_raw WHERE track_id NOT IN (SELECT track_id FROM bronze.spotify_tracks)` → batches of 50
  - `tracks?ids=...` → INSERT bronze.spotify_tracks
  - Same for artists
- `orchestration/dagster/assets/spotify.py` — three new assets + schedules:
  - `spotify_recently_played` — `@schedule(cron_schedule='*/1 * * * *')` (1 min)
  - `spotify_saved_tracks` — `@schedule(cron_schedule='*/5 * * * *')` (5 min)
  - `spotify_metadata_enricher` — `@sensor(minimum_interval_seconds=600)` (10 min, triggers an enrichment run when unknown IDs detected)
- `transformations/models/silver/silver_spotify_plays.sql` — dbt incremental, denormalized join of plays × tracks × artists
- `transformations/models/silver/silver_spotify_saved.sql` — passthrough cleanup
- `transformations/models/gold/`:
  - `gold_spotify_recent_tracks.sql` (view)
  - `gold_spotify_kpis_summary.sql` (table, materialized incrementally)
  - `gold_spotify_kpis_dashboard.sql` (table)
  - `gold_spotify_top_artists.sql` (table, includes 30-day trend array)
  - `gold_spotify_genres.sql` (view)
  - `gold_spotify_daily_listening.sql` (view)
- `transformations/models/schema.yml` — add `tests:` for not_null/uniqueness on key columns
- Update `ingestion/spotify/authenticate_local.py` scope list to add `user-library-read`
- Update `scripts/check_audio_features.py` is removed (no longer relevant)

**Verify**:
- `scripts/verify_phase_2.py`:
  - All `gold.gold_spotify_*` tables return rows
  - `dbt test` passes
  - `curl /api/spotify/{summary,data,recent}` → all `_meta.cached: false`
  - `bronze.spotify_saved_tracks` count > 0 after the user re-runs auth

> 🛑 **USER ACTION**: after Phase 2 lands, re-run `.venv/bin/python ingestion/spotify/authenticate_local.py` to upgrade the cache file with the `user-library-read` scope. Without this, the saved-tracks producer 401s.

---

### Phase 3 — Cross-source events plumbing

**Goal**: `silver.events_unified` accepting projections from any source; `gold.gold_home_recent_events` and `gold.gold_home_overview_stats` live (Spotify-only initially).

**Depends on**: Phase 2.

**Build**:
- `warehouse/ddl/30_events_unified.sql` — `silver.events_unified` table (schema per DATA_MODEL.md)
- `transformations/models/silver/`:
  - `silver_events_unified_spotify_plays.sql` — projects `silver_spotify_plays` → events_unified shape with `kind='play'`
  - `silver_events_unified_spotify_liked.sql` — projects `silver_spotify_saved` → events_unified with `kind='liked'`
  - These are dbt `materialized='materialized_view'` writing into the shared `silver.events_unified` storage table
- `transformations/models/gold/`:
  - `gold_home_recent_events.sql` — top 10 per source as described in DATA_MODEL.md
  - `gold_home_overview_stats.sql` — cross-source totals (Spotify counts only for now)
  - `gold_home_daily_data_generation.sql` — per-day counts (Spotify only for now)

**Verify**:
- `scripts/verify_phase_3.py`:
  - `silver.events_unified` count > 0
  - `gold.gold_home_recent_events` returns ≤10 spotify rows
  - `curl /api/overview/stats` → live numbers for spotify columns, 0s for youtube/maps/calendar (expected)
  - `curl /api/home/recent-events` → spotify[] populated, youtube[]/maps[] empty (expected)

---

### Phase 4 — Google OAuth foundation + weekly re-auth dance

**Goal**: A persisted Google refresh-token + access-token pair in `auth.google_tokens`, automatically refreshed in-process, with a Pages Function for browser re-auth.

**Depends on**: Phase 0 (auth.google_tokens already exists), §1.2 USER ACTION done (Google Cloud Console setup), §1.4 USER ACTION done (webhook secrets).

**Build**:

**Backend (Dagster)**:
- `ingestion/_shared/google_oauth.py`:
  - `class GoogleCredentials` — wraps `google.oauth2.credentials.Credentials`
  - `load_from_clickhouse(account_email)` — reads latest row from `auth.google_tokens`
  - `persist_to_clickhouse(creds)` — UPSERT into `auth.google_tokens`
  - `refresh_if_needed(creds)` — calls `creds.refresh(Request())` if `access_token` near expiry; persists rotated tokens
- `orchestration/dagster/resources.py` — fill in `GoogleAuthResource`:
  - `setup_for_execution()` reads tokens from ClickHouse
  - `get_credentials()` returns a fresh `Credentials` (refreshing if needed)
  - `account_email` is configurable; defaults to first row in table
- `orchestration/dagster/assets/google_auth.py`:
  - `google_token_health` — `@schedule(cron_schedule='0 9 * * 1')` (Monday 09:00 weekly):
    - SELECT `issued_at` from `auth.google_tokens`
    - If > 6 days old: INSERT row into `auth.alerts` with `kind='token_expiring'`
    - Optional Phase 8: send email via Cloudflare Email Service

**Frontend (Cloudflare Pages Functions)**:
- `dashboard/functions/api/_internal/google-auth-redirect.ts`:
  - GET endpoint, validates a session/Cookie or simple shared-secret in query
  - Builds Google OAuth URL with the full scope list + `state=<random_nonce_signed_with_GOOGLE_REAUTH_STATE_SECRET>`
  - Returns 302 to that URL
- `dashboard/functions/api/_internal/google-auth-callback.ts`:
  - GET endpoint, validates `state` against the signing secret (prevents CSRF)
  - Takes `?code=...`, POSTs to `https://oauth2.googleapis.com/token` with `client_id`, `client_secret`, `redirect_uri`, `grant_type=authorization_code`
  - On success: INSERT/UPSERT into `auth.google_tokens` via the existing tunnel + Access service token (using `queryClickHouse` helper already in `dashboard/functions/_shared/`)
  - Returns simple HTML "Re-auth complete. You can close this tab. Next renewal due <date+7days>."
- `dashboard/functions/_shared/types.ts` — add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REAUTH_STATE_SECRET` to the `Env` type
- `dashboard/scripts/deploy-to-pages.sh` — uploads the new secrets from `.env.production`

**Bootstrap script (one-time, on laptop)**:
- `scripts/bootstrap_google_auth.py` — runs the OAuth flow locally on `http://127.0.0.1:8000/callback`, writes the resulting tokens directly into ClickHouse via the local tunnel (`clickhouse-connect` to `https://clickhouse.<DOMAIN>` with Access service token). Used once to seed the table before the Pages re-auth path is needed.

**Verify**:
- `scripts/verify_phase_4.py`:
  - `auth.google_tokens` has ≥1 row
  - `python -c "from ingestion._shared.google_oauth import GoogleCredentials; c = GoogleCredentials.load_from_clickhouse('YOUR_EMAIL'); print(c.access_token[:10])"` returns first 10 chars of a valid token
  - `curl https://<PAGES_DOMAIN>/api/_internal/google-auth-redirect` returns 302 to Google
  - Walk through the full re-auth flow in browser; new row appears in `auth.google_tokens`

> 🛑 **USER ACTION**: After Phase 4 build completes, run `python scripts/bootstrap_google_auth.py` once on your laptop to seed the first token. Subsequent re-auths happen via the Pages link.

---

### Phase 5 — Maps via Data Portability API

**Goal**: 1y of Maps Timeline data in `bronze.maps_*`; trip segmentation populating `silver.maps_trips`; `/api/travel/data` live with real numbers.

**Depends on**: Phase 4 (GoogleAuthResource working).

**Build**:
- `warehouse/ddl/50_maps.sql` — bronze tables + `silver.maps_home_locations` + `silver.maps_trips` (schemas per DATA_MODEL.md)
- `ingestion/google/portability.py` (shared with YouTube):
  - `class DataPortabilityClient(creds: Credentials)`
  - `initiate_archive(resource_scopes: list[str], start_time, end_time) -> archive_job_id`
  - `wait_for_archive(job_id, timeout_s=3600) -> list[signed_urls]`
  - `download_archive(signed_urls, dest_dir)` → returns unpacked directory
- `ingestion/google/maps/parser.py`:
  - Walks the unpacked archive, finds Timeline JSON files (`Maps/Timeline/*.json` historically; verify path against your actual archive)
  - Parses `placeVisit` → list of bronze rows for `maps_visits` (extracting `place_address` from `placeAddress` field)
  - Parses `activitySegment` → list of bronze rows for `maps_path`
  - Returns DataFrames or lists of dicts
- `ingestion/google/maps/insert.py` — INSERT helpers using clickhouse-connect's bulk API
- `orchestration/dagster/assets/google.py`:
  - `maps_initial_backfill` — one-shot asset, takes a `years_back` config (default 1)
  - `maps_daily_incremental` — `@schedule(cron_schedule='0 4 * * *')` (4 AM daily)
    - Initiates DP archive for last 24h
    - Downloads + parses + inserts
- `scripts/probe_maps_data_portability.py` — calls DP for just Maps with a 7-day window, reports row counts. Run this once after Phase 4 to verify Maps Timeline is still in the cloud (not migrated on-device).
- `silver.maps_home_locations` seeding:
  - `scripts/set_home_location.py` — interactive CLI: prompts user for lat/lng + radius_km, INSERTs row. User runs once on laptop after Phase 5 lands.
- `transformations/models/silver/`:
  - `silver_maps_visits.sql` — cleanup + extract city/country from `place_address` (regex)
  - `silver_maps_trips.sql` — **not a dbt model — see note below**
- `orchestration/dagster/assets/google.py` — `maps_trip_segmentation` asset (Python, not SQL):
  - Reads bronze + home anchor
  - Implements the 4-step segmentation algorithm from DATA_MODEL.md
  - Writes to `silver.maps_trips` via TRUNCATE+INSERT (small table, full rebuild is fine)
  - Triggered after each successful `maps_daily_incremental` run
- `transformations/models/gold/`:
  - All 6 gold_maps_*_dashboard tables (schemas + columns derived from `dashboard/functions/api/travel/data.ts`)
  - `gold_maps_trips.sql` — `SELECT * FROM silver.maps_trips ORDER BY started_at DESC` (not yet queried by the handler but landed for future use)
- Update `silver.events_unified_maps_*.sql` dbt models to project maps visits into events_unified with `kind='place_visit'`

**Verify**:
- `scripts/verify_phase_5.py`:
  - `bronze.maps_visits` count > 0 after probe
  - `silver.maps_home_locations` count = 1 after seed
  - `silver.maps_trips` count >= expected (eyeball: ~5-10 trips per year of personal data)
  - `curl /api/travel/data` returns real numbers; `_meta.cached: false`

> 🛑 **USER ACTION (post-Phase 5)**: run `python scripts/probe_maps_data_portability.py` to verify Timeline is cloud-accessible. If empty, switch to manual on-device exports — auto-mode will leave `scripts/import_maps_timeline_export.py` ready for this case.

---

### Phase 6 — YouTube DP history + Data API v3 enrichment

**Goal**: 1y of YouTube history in bronze; `bronze.youtube_videos`/`channels` populated by v3 enricher; `/api/youtube/data` live with real numbers (watch-time as labelled proxy).

**Depends on**: Phase 4 + Phase 5 (DataPortabilityClient already exists).

**Build**:
- `warehouse/ddl/60_youtube.sql` — bronze tables: history, search, videos, channels
- `ingestion/google/youtube/parser.py` — walks DP archive, parses `youtube/history/watch-history.json` + `youtube/history/search-history.json`
- `ingestion/google/youtube/enricher.py`:
  - `class YouTubeDataAPIClient(creds)` — wraps `googleapiclient.discovery.build('youtube', 'v3', credentials=creds)`
  - `enrich_videos(video_ids: list[str], batch_size=50)` → list of dicts → INSERT into `bronze.youtube_videos`
  - `enrich_channels(channel_ids: list[str], batch_size=50)` → INSERT into `bronze.youtube_channels`
  - Static mapping `YOUTUBE_CATEGORY_NAMES = {...}` loaded once from `videoCategories.list`
- `orchestration/dagster/assets/google.py`:
  - `youtube_history_daily` — `@schedule` 4:30 AM daily, DP archive for last 24h, parse, INSERT
  - `youtube_history_initial_backfill` — one-shot, 1y window
  - `youtube_metadata_enricher` — `@sensor` every 10 min, detects unknown video_id, batches against v3
- `transformations/models/silver/silver_youtube_watches.sql` — join history × videos × channels
- `transformations/models/silver/silver_youtube_searches.sql`
- `transformations/models/gold/` — 6 gold_youtube_*_dashboard tables; the watch-time ones compute `count × videos.duration_seconds`, with SQL comments explicitly calling it a proxy
- Update events_unified projection for YouTube (kind='watch')

**Verify**:
- `scripts/verify_phase_6.py`:
  - `bronze.youtube_watch_history` count > 0
  - `bronze.youtube_videos` count grows as enricher runs (within 30 min)
  - `gold.gold_youtube_top_channels_dashboard` returns 10 rows
  - `curl /api/youtube/data` → `_meta.cached: false`, sensible numbers

---

### Phase 7 — Calendar push pipeline

**Goal**: Live event-driven Calendar ingest with the 60s-polling fallback ready.

**Depends on**: Phase 4 + §1.4 USER ACTION (CALENDAR_WEBHOOK_TOKEN in Pages secrets).

**Build**:

**Pages Function**:
- `dashboard/functions/api/_internal/calendar-webhook.ts`:
  - POST endpoint, validates `X-Goog-Channel-Token` against `env.CALENDAR_WEBHOOK_TOKEN`
  - Reads `X-Goog-Channel-ID`, `X-Goog-Message-Number`, `X-Goog-Resource-ID`, `X-Goog-Resource-State`
  - INSERTs into `bronze.calendar_sync_notifications` via the tunnel + service token
  - Returns 200 quickly (Google requires fast 2xx; retries on 5xx)

**Dagster**:
- `warehouse/ddl/70_calendar.sql` — bronze tables (events + sync_notifications) + `silver.calendar_category_aliases`
- `ingestion/google/calendar/`:
  - `client.py` — `class CalendarClient(creds)`, methods: `list_calendars()`, `events_list(calendar_id, sync_token=None) -> (events, next_sync_token)`, `events_watch(calendar_id, webhook_url, channel_id, token) -> (channel_id, resource_id, expiration)`
  - `parser.py` — Google `Event` JSON → `bronze.calendar_events` row (handles `recurringEventId`, status, attendee count)
- `orchestration/dagster/assets/google.py`:
  - `calendar_channels_setup` — one-shot, iterates `list_calendars()`, calls `events.watch` for each, stores channel metadata in `auth.calendar_channels` table (new, add to `02_auth_tables.sql`)
  - `calendar_channels_renew` — `@schedule(cron_schedule='0 6 * * *')` (daily 6 AM), re-watches each channel with a new ID before the 7-day TTL
  - `calendar_sync_sensor` — `@sensor(minimum_interval_seconds=30)`:
    - SELECT unprocessed rows from `bronze.calendar_sync_notifications`
    - For each affected `calendar_id`: read stored `sync_token` from `auth.calendar_channels`, call `events.list?syncToken=…`, INSERT delta into `bronze.calendar_events`, advance `sync_token`, mark notification processed
  - `calendar_polling_fallback` — `@schedule(cron_schedule='*/1 * * * *')` (1 min), disabled by default. If webhook breaks, flip a config flag to enable; same logic minus the webhook trigger
- `transformations/models/silver/silver_calendar_events.sql` — cleanup + `category` derivation:
  - LEFT JOIN `silver.calendar_category_aliases` on `calendar_name`
  - `coalesce(alias.display_category, calendar_name)` AS `category`
- `transformations/models/gold/` — all 7 gold_calendar_* tables: kpis, busy_hours, categories, weekday_breakdown, daily_events, week_grid, upcoming_events
- Add events_unified projection for Calendar (kind='meeting')
- Update `dashboard/public/_redirects` to remove `/api/google/calendar` (we'll have a real handler) → write `dashboard/functions/api/google/calendar.ts` querying the new gold tables

**Verify**:
- `scripts/verify_phase_7.py`:
  - `auth.calendar_channels` count > 0 (channels active)
  - Create a test event in Google Calendar → within 30s `bronze.calendar_events` has the new row → `bronze.calendar_sync_notifications` has the trigger marked processed
  - `curl /api/google/calendar` returns real numbers; `_meta.cached: false`

> 🛑 **USER ACTION (post-Phase 7)**: re-deploy Pages once to ship the new functions: `cd dashboard && nvm use 22 && ./scripts/deploy-to-pages.sh`.

---

### Phase 8 — Observability + finishing touches

**Goal**: `/api/system/health` populated; token-expiry alerts visible; production hardening.

**Depends on**: Phases 1-7 deployed.

**Build**:
- `dashboard/functions/api/system/health.ts` — queries:
  - Each `bronze.<source>_*._ingested_at` MAX → `lastBatchAgo`
  - Last 24h INSERT rate → `eventsPerHour`
  - `system.parts` for storage stats (rowCount, diskUsedMb)
  - `system.events` for query latency (P50/P99)
  - `auth.alerts` for active warnings
- Remove `/api/system/health` from `dashboard/public/_redirects`
- `orchestration/dagster/assets/observability.py`:
  - `freshness_monitor` — daily `@schedule`, checks bronze table freshness, INSERTs to `auth.alerts` if any source is stale
  - Optional: email via Cloudflare Email Service when an alert is raised (stretch — wire only if user wants notifications outside the Dagster UI)
- `transformations/dbt_project.yml` — add `on-run-end` hook to run `dbt test` and fail loudly if any source is missing data
- `README.md` — refresh with link to IMPLEMENTATION_PLAN.md, OPERATIONS.md, DATA_MODEL.md, PIPELINES.md as the four canonical docs
- `OPERATIONS.md` — update the "Post-deploy follow-ups" section: remove "VM ClickHouse data migration / repopulation" (no longer applicable); add a "Weekly Google re-auth" workflow note

**Verify**:
- `scripts/verify_phase_8.py`:
  - `curl /api/system/health` returns all-green per-source statuses with freshness < 24h for daily sources, < 5min for Spotify, < 5min for Calendar
  - `auth.alerts` has no `kind='auth_failed'` rows
- All gold tables tested via `dbt test`

---

## 4. Verification matrix

| Phase | Quickest signal | Definitive check |
|---|---|---|
| 0 | `docker compose ps` shows all healthy | `dbt debug` ✅ |
| 1 | Dashboard "Now Playing" tile shows real track | `scripts/verify_phase_1.py` |
| 2 | `/api/spotify/data` shows real numbers | `scripts/verify_phase_2.py` |
| 3 | `/api/home/recent-events` spotify[] populated | `scripts/verify_phase_3.py` |
| 4 | `auth.google_tokens` has 1 row | OAuth round-trip via the Pages link |
| 5 | `bronze.maps_visits` has rows | `silver.maps_trips` ≥ expected |
| 6 | `bronze.youtube_videos` populated by enricher | `gold.gold_youtube_top_channels_dashboard` ≠ empty |
| 7 | Edit a Google Calendar event → bronze row appears within 30s | `auth.calendar_channels` shows active channel |
| 8 | `/api/system/health` shows all-green | `dbt test` passes |

## 5. Known risks + escape hatches

| Risk | Likelihood | Escape hatch |
|---|---|---|
| Google refresh tokens expire weekly | **certain** (it's the design) | Weekly re-auth dance (Phase 4); long-term verify OAuth app |
| Maps Timeline is on-device only | possible | `scripts/probe_maps_data_portability.py` after Phase 4; fall back to manual on-device exports |
| YouTube Data API v3 quota exhaustion | very unlikely at personal scale | Enricher retries next day; quota resets at midnight Pacific |
| dbt-clickhouse MV materializations break on edge cases | low-medium | Each MV model has a fall-back `materialized='table'` variant in comments |
| Cloudflare Pages Function 1MB bundle size | low | Webhook + callback functions are tiny; remove unused npm deps |
| Refresh-token rotation invalidates concurrent runs | low (single-user) | `auth.google_tokens` ReplacingMergeTree with `_updated_at` version always picks the latest |
| Calendar push channel TTL ambiguity | medium | Renew daily not weekly; assume max 7 days |
| Reverse-geocoding country parsing fails on non-Latin addresses | medium | Static country-borders lookup as fallback (no API needed) |

## 6. Out of scope (deferred)

- Email notifications (Cloudflare Email Service) — Phase 8 stretch
- GitHub Actions / CI — manual deploys only
- Google OAuth verification submission — post-launch
- dbt Cloud / dbt artifacts upload — local target/ folder is enough
- Audio features tiles (Spotify blocked these for our app)
- Spotify recently-played pagination with `before` cursor for >50 deep history — only needed once we add `Spotify Extended Streaming History` manual import
