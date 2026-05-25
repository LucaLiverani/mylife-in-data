# Pipelines

The next workstream: build the ingest + transform + serve loop on the new Dagster + Redpanda + ClickHouse stack. Until this is done, the dashboard serves bundled mocks transparently.

## Goal shape

```
  Source                Ingest                       Stream / batch        Warehouse                Dashboard
  ──────                ──────                       ─────────────         ─────────                ─────────
  Spotify Web API ────► spotify producer            Redpanda topic        ClickHouse Kafka         /api/spotify/current
   (OAuth, polling)     ingestion/spotify/*.py      spotify.player.       engine table →           live track tile
                                                    current                bronze + gold

  Spotify Web API ────► spotify backfill            (direct INSERT)       gold_spotify_*           /api/spotify/{summary,data,recent}
   (history)            scheduled Dagster asset                                                     KPIs, top artists, daily listening

  Google APIs ────────► google ingestion            (direct INSERT)       gold_youtube_*           /api/youtube/data
   (Data Portability    ingestion/google/youtube/                          gold_maps_*              /api/travel/data
   + YouTube Data v3)   + maps/ parsers                                    gold_home_*              /api/overview/stats, /api/home/recent-events

  Google Calendar ────► events.watch webhook        (direct INSERT)       gold_calendar_*          /api/google/calendar
   API (push, OAuth)    + Dagster sync sensor
```

The dashboard already expects this shape (see `dashboard/functions/api/*.ts` for the queries each endpoint runs). Replicate the column names + shapes from the mock files in `dashboard/public/mocks/<path>.json` — those are the contract.

## Directory layout

What exists today:

```
ingestion/spotify/
  authenticate_local.py    # OAuth handshake — KEEP, this is the only piece from the legacy code
orchestration/dagster/
  definitions.py           # placeholder code location, just a sanity-check asset
```

What's coming (proposed):

```
ingestion/
  spotify/
    authenticate_local.py
    producer.py            # poll Spotify "currently playing", produce to Redpanda
    backfill.py            # paginate recently-played history, INSERT directly to bronze
  google/
    portability.py         # Data Portability API client: initiate → poll → download → unpack
    youtube/parser.py      # parse YouTube watch + search history JSON (same payload as Takeout)
    maps/parser.py         # parse Maps Timeline JSON (same payload as Takeout)
    calendar/producer.py   # ICS or Calendar API → Redpanda or direct INSERT
  _shared/
    clickhouse.py          # python-clickhouse-connect client + retry policy
    redpanda.py            # kafka-python producer wrapper

orchestration/dagster/
  definitions.py           # exposes all assets + schedules
  resources.py             # ClickHouseResource, RedpandaResource, SpotifyResource (loads OAuth cache)
  assets/
    spotify.py             # @asset for backfill, @schedule for hourly refresh
    google.py              # @asset for each Takeout-derived source
    transformations.py     # @dbt_assets bridge once we have dbt models

transformations/            # dbt project (decide: keep separate or fold into Dagster?)
  models/
    bronze/                # raw landing tables (1:1 with producers + parsers)
    silver/                # cleaned, deduped, joined where appropriate
    gold/                  # dashboard-facing aggregates (must match the dashboard's expected schema)
  profiles.yml             # gitignored — local + VM connection strings

warehouse/
  ddl/
    redpanda_engine_tables.sql   # ClickHouse Kafka-engine tables that consume topics
    materialized_views.sql       # bronze → silver lift if not using dbt for those
```

## First pipeline to build

**Spotify current-track** is the natural first target:

1. The OAuth flow is already in `ingestion/spotify/authenticate_local.py` (the *only* thing we kept from the legacy code).
2. It exercises every layer: producer (`ingestion/`) → broker (`Redpanda`) → engine (`ClickHouse Kafka engine`) → bronze view → gold view → endpoint (`/api/spotify/current` already exists, just needs the `gold.gold_spotify_current_track` table to exist).
3. It's the most visible win in the dashboard (live "Now Playing" tile).

Suggested sequence:
1. Port `get_spotify_producer_client()` from the legacy `spotify_api.py` to a Dagster `ConfigurableResource` that reads from `DAGSTER_HOME/.spotify_cache` (CacheFileHandler pattern).
2. Write `ingestion/spotify/producer.py` — runs as a long-lived Dagster sensor or a tight-loop asset that polls `me/player/currently-playing` every ~5s and publishes to the `spotify.player.current` topic.
3. Create the Redpanda topic (already exists per Phase 1.1) and the ClickHouse Kafka-engine consumer (`warehouse/ddl/bronze_spotify_current_track_kafka.sql` was referenced in the deploy plan — write the new version pointing at `redpanda:9092`).
4. Add a gold view `gold.gold_spotify_current_track` whose shape matches `dashboard/public/mocks/spotify/current.json`.
5. The dashboard endpoint `/api/spotify/current` should automatically start showing live data (it's already wired through `queryWithFallback`).

When live data flows, the dashboard's "ClickHouse offline" badge disappears and `_meta.cached` flips to `false`.

## Local development → production deployment

The platform layer is identical between laptop and VM (same compose stack, same ClickHouse schema, same Dagster code location). A pipeline that runs locally should run on the VM with minimal extra work. The interesting parts are credentials and source-data shipping.

### What lives where

| Layer | Tracked in git? | Where it lives | How it gets to the VM |
|---|---|---|---|
| **Pipeline code** (Python, SQL, dbt models) | yes (`dev` branch) | `ingestion/`, `orchestration/`, `transformations/` | `git push origin dev` → `ssh; git pull origin dev` |
| **OAuth app credentials** (`SPOTIFY_CLIENT_ID`, `GOOGLE_CLIENT_ID`, etc.) | no | `infrastructure/.env` (gitignored) | Edit the VM's copy of `infrastructure/.env` once |
| **OAuth user token cache** (`.spotify_cache`, `google_token.json` — the refresh_token cookie that proves consent) | no, never | Dagster home volume on each machine | Authenticate locally, scp the cache file to the VM, drop it into the Dagster home path |
| **Source data archives** (Data Portability downloads, optional Takeout/Timeline fallbacks, `.ics` exports) | no | producer-managed (e.g. `~/landing/` or R2) | Data Portability fetched in-pipeline; manual paths scp'd or `aws s3 cp` for one-offs |
| **PERSONAL.md** | no | repo root, gitignored | Stays on your laptop |

### Auth flow — Spotify (template for any OAuth source)

The Spotify producer needs (a) app credentials registered in the Spotify developer console and (b) a per-user refresh_token cached after a one-time browser handshake. Step-by-step:

**One-time on the laptop:**
```bash
# 1. Register the app at https://developer.spotify.com/dashboard
#    Add a redirect URI like http://localhost:8888/callback
# 2. Drop the values into infrastructure/.env (gitignored):
#    SPOTIFY_CLIENT_ID=...
#    SPOTIFY_CLIENT_SECRET=...
#    SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
# 3. Run the browser handshake:
python ingestion/spotify/authenticate_local.py
# This produces a cache file (legacy default: ~/.spotipy_token_cache, but
# the rewritten code should point Spotipy's CacheFileHandler at
# <DAGSTER_HOME>/.spotify_cache so the Dagster resource finds it).
```

**One-time on the VM:**
```bash
# 1. Add the same SPOTIFY_* values to the VM's infrastructure/.env
ssh <VM_USER>@<VM_IP>
$EDITOR ~/mylife-in-data/infrastructure/.env   # paste the SPOTIFY_* lines, save
# (Restart the Dagster containers after editing .env so the new values load:
#  cd ~/mylife-in-data/infrastructure && ./stop-all.sh && ./start-all.sh)

# 2. Ship the user-token cache. Dagster runs in a container, so the cache
#    file needs to land inside the dagster-home volume. Easiest path:
#    a) scp the file to the VM host, then
#    b) docker cp it into the dagster-webserver container at /opt/dagster/dagster_home/
#    (Or, change infrastructure/compose/dagster/docker-compose.yml to bind-mount
#    a host directory as DAGSTER_HOME so scp lands the file directly.)

scp ~/path/to/.spotify_cache <VM_USER>@<VM_IP>:/tmp/.spotify_cache
ssh <VM_USER>@<VM_IP> 'docker cp /tmp/.spotify_cache dagster-webserver:/opt/dagster/dagster_home/.spotify_cache'
```

After this, the Dagster `SpotifyResource` opens the cache file at startup, reads the refresh_token, and uses Spotipy's auto-refresh to keep `access_token` fresh on its own. **You only ever re-authenticate (and re-scp) if you revoke consent in Spotify's account dashboard or if Spotify expires the refresh_token (rare; multi-month TTL).**

Same pattern for **all Google sources** (YouTube + Maps via the Data Portability API, Calendar via the Calendar API or `.ics` poll) — register one app in the Google Cloud Console, enable the scopes you need, drop `GOOGLE_*` into `infrastructure/.env`, run a one-shot auth script, drop the resulting token JSON into the Dagster home alongside `.spotify_cache`. A single Google OAuth app can cover all three sources if you enable each scope on it.

### Source data — Google Data Portability API (OAuth, programmatic)

For **Maps**, Data Portability is the only viable programmatic path —
Google deprecated other Maps Timeline access. For **YouTube** the API is
**TBD**: Data Portability returns the same watch + search history payload
as Takeout, while YouTube Data API v3 has richer per-video / per-channel
metadata but Google deprecated reliable watch-history endpoints in 2016.
The two can be combined (DP for raw history rows, v3 for enrichment).

The flow below describes the **Data Portability** path — certain for Maps,
candidate for YouTube. If YouTube ends up on Data API v3 instead, steps
1–3 are replaced by direct REST queries against `/videos`, `/channels`,
`/activities` — same bronze schema, different producer.

One Google Cloud Console app, OAuth'd once, can cover all three (DP
scopes + YouTube Data API + Calendar API) — each scope enabled
individually. Each Data Portability ingest tick is:

1. **`archives.initiate`** — Dagster schedule POSTs the list of resource
   scopes it wants (e.g. `dataportability.youtube.activity`,
   `dataportability.youtube.searches`,
   `dataportability.maps.starred_places`). Returns an `archiveJobId`.
2. **Poll** `archiveJobs.getPortabilityArchiveState` until status flips to
   `COMPLETE` (minutes for incremental, longer on the first backfill).
3. **Download** each signed URL → unpack the zip. Layout matches Google
   Takeout 1:1 (same JSON file paths and shapes), so parsers are
   interchangeable between the two paths.
4. **INSERT into bronze.** `ReplacingMergeTree(_ingested_at)` collapses
   any row overlapping a previous run, so a day's archive is safe to
   re-fetch without duplicates.

Apps stay in **"testing" mode** for self-only use — you're the only test
user, no Google brand verification needed. Same pattern as the Spotify
dev app.

**Caveat — Maps Timeline**: Google migrated Maps location history to
on-device storage in late 2024 / early 2025. Pre-migration data is still
in Data Portability; new visits may only live in your phone's local
Timeline. Fallback is the on-device "Export Timeline" feature (periodic
manual export, parsed by the same `maps/parser.py`).

**Initial backfill**: one big archive job covering all-time history
(slow but unattended). **Incremental**: a daily Dagster schedule requests
just the last day's archive — cheap, small, completes in minutes.

Manual Takeout (`https://takeout.google.com/`) remains a usable fallback
for one-shot loads or if the API path breaks; the parsers don't care
which path the archive came from. Long-term: stage downloads in R2
rather than VM-local landing if multiple backfills risk filling the disk.

### Calendar push architecture

Google Calendar API exposes `events.watch`: register a webhook URL per
calendar, and Google POSTs a notification when any event in that calendar
is created / modified / deleted. That's our event-driven ingest — same
latency story as the Spotify "Now playing" tile, just driven by Google's
push rather than our poll.

Flow:

1. **One-time setup per calendar** — Dagster asset calls
   `calendars.events.watch(calendarId, channelId, address, token)`. Google
   returns `resourceId` + `expiration` (max 7-day TTL). We persist the
   channel metadata so we can renew before expiration.
2. **Push receipt** — Google POSTs to a Cloudflare Pages Function at
   `https://<PAGES_DOMAIN>/api/internal/calendar-webhook`. The function
   validates `X-Goog-Channel-Token` against our secret, INSERTs a row
   into `bronze.calendar_sync_notifications` over the same tunnel +
   Access service token that the dashboard already uses, and returns
   200 quickly (Google retries on slow/failed responses).
3. **Sensor pickup** — A Dagster sensor ticks every ~30s, SELECTs
   unprocessed rows from the sync queue, and for each affected calendar
   calls `events.list?syncToken=…` for the delta. Delta lands in
   `bronze.calendar_events`; syncToken advances; notification is marked
   processed.
4. **Channel renewal** — Separate Dagster schedule re-watches each
   channel daily (before the 7-day expiration) to keep the push alive.

Categorization is free: every event carries `calendarId`, and we use
`calendar_name` directly as the category. Pretty-printing (if raw calendar
names need it) goes in `silver.calendar_category_aliases`.

**Fallback** if the webhook plumbing is more friction than it's worth:
drop steps 1–2 and run a Dagster schedule every 60s calling
`events.list?syncToken=…` for each calendar. Same delta logic minus the
webhook receiver. Latency rises from seconds to minute-scale; everything
else is identical.

### The day-to-day loop

```
[laptop]  edit code → run/test against local CH (./start-all.sh)
          git commit + git push origin dev
[laptop]  ssh <VM_USER>@<VM_IP> 'cd mylife-in-data && git pull origin dev'
[VM]      dagster picks up modified Python on its next code-server reload
          (or restart explicitly: docker compose -f infrastructure/compose/dagster/docker-compose.yml restart)
[laptop]  watch dagster.<DOMAIN> for runs, grafana.<DOMAIN> for metrics
          when stable: git checkout main && git merge --ff-only dev && git push origin main
```

Compose configs already match between laptop and VM, so the only laptop-only oddity is the port override (`DAGSTER_PORT=3030`) if you have something else holding `:3000`. The VM uses the default.

### What you'll never need to ship via git

- `.spotify_cache`, `google_token.json`, any per-user OAuth artifact — these are credentials, gitignored
- `infrastructure/.env` — gitignored, edited by hand on each machine
- Raw export archives (Data Portability downloads, fallback Takeout zips, on-device Timeline exports) — gitignored, fetched in-pipeline or scp'd for one-offs, optionally staged in R2
- `PERSONAL.md` — your placeholder cheat-sheet, gitignored

---

## Open architectural questions

Decisions to make before writing real code:

1. **dbt vs Dagster-native SQL assets?** Either works. `dagster-dbt` is well-supported; pure `@asset` with embedded SQL keeps everything in one tool. The legacy stack used dbt — leaning that way for continuity.
2. **R2 vs MinIO for raw landing?** MinIO no longer starts on the VM. R2 is the long-term target. Producers could write raw payloads to R2 first (for replay-ability), then INSERT to ClickHouse — or skip the lake entirely for low-volume sources.
### Resolved (2026-05-24)

3. ~~Backfill strategy~~ → **1 year initial pull** via each source's API. Deeper history filled later by one-shot manual exports (Spotify "Account Privacy → Request data" Extended Streaming History; Google Takeout zips; on-device Maps Timeline exports) — same Dagster parser assets, run only after live pipelines are stable so no data is missed on cutover.
4. ~~Calendar source~~ → **Google Calendar API + `events.watch` push notifications.** Multi-calendar import; `calendar_name` is the category directly. Fallback: 60s incremental polling with `syncToken`. See the "Calendar push architecture" subsection above for the full flow.
5. ~~YouTube API choice~~ → **Hybrid.** Data Portability for the raw watch + search history rows; YouTube Data API v3 as a `video_id → channel/category/duration` enricher (Dagster sensor, batched 50 IDs/call). Watch-time tiles stay an explicit `count × duration_seconds` proxy — Google doesn't track partial-watch time anywhere.

## What to leave alone

- `dashboard/functions/api/*.ts` — they're already wired to query the `gold.*` tables that the pipelines will create. No changes needed there once the warehouse catches up.
- `dashboard/public/mocks/*.json` — the contract. Pipelines should match these shapes, not the other way around. Update mocks only if the underlying data model genuinely changes.
- `infrastructure/compose/*` — the platform layer is done. Pipelines run as Dagster assets inside the existing webserver/daemon containers.

## When this is done

The "Post-deploy follow-ups" section of OPERATIONS.md gets shorter. The first follow-up to remove is "VM ClickHouse data migration / repopulation" — that becomes "the pipelines populate gold.* as they run." The `_meta.cached: true` signal on every endpoint flips to `false` and the dashboard renders the user's actual data.
