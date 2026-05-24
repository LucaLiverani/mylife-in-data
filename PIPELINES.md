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

  Google Takeout ─────► takeout parser              (direct INSERT)       gold_youtube_*           /api/youtube/data
   (manual upload)      ingestion/google/youtube/                          gold_maps_*              /api/travel/data
                        + maps/                                            gold_home_*              /api/overview/stats, /api/home/recent-events

  Google Calendar ────► calendar producer (TBD)     Redpanda or direct    gold_calendar_*          /api/google/calendar
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
    youtube/parser.py      # parse Google Takeout YouTube history JSON
    maps/parser.py         # parse Google Maps Timeline JSON
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
| **Source data files** (Google Takeout zips, .ics exports) | no | wherever the pipeline expects (e.g. `~/landing/` or R2) | scp / `aws s3 cp` once per backfill |
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

Same pattern for **Google Calendar** if you go the OAuth route — register the app in the Google Cloud Console, drop `GOOGLE_*` into `infrastructure/.env`, run a one-shot auth script, scp the resulting token JSON into the Dagster home.

### Source data — Google Takeout (file-based, no OAuth)

Takeout is a manual export, not an API. Workflow:

1. Request the export at <https://takeout.google.com/> (YouTube history + Maps Timeline). Wait for the email (can take hours).
2. Download to laptop.
3. scp into a known landing path on the VM:
   ```bash
   scp ~/Downloads/takeout-2026-05-24-*.zip <VM_USER>@<VM_IP>:~/landing/
   ```
4. A Dagster sensor on `~/landing/*.zip` triggers the parser asset that unpacks → cleans → INSERTs into bronze. Long-term: switch from VM-local landing to R2 so multiple backfills don't fill the VM disk.

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
- Takeout exports / raw source files — gitignored, scp'd or stored in R2
- `PERSONAL.md` — your placeholder cheat-sheet, gitignored

---

## Open architectural questions

Decisions to make before writing real code:

1. **dbt vs Dagster-native SQL assets?** Either works. `dagster-dbt` is well-supported; pure `@asset` with embedded SQL keeps everything in one tool. The legacy stack used dbt — leaning that way for continuity.
2. **R2 vs MinIO for raw landing?** MinIO no longer starts on the VM. R2 is the long-term target. Producers could write raw payloads to R2 first (for replay-ability), then INSERT to ClickHouse — or skip the lake entirely for low-volume sources.
3. **Backfill strategy for Google Takeout?** Manual upload to a known path → Dagster sensor → parser → bronze. Or skip the orchestrator for one-shot loads and just run a python script.
4. **Calendar source?** Google Calendar API (needs OAuth) vs published `.ics` URL (no OAuth, polling). The latter is much simpler if it fits the use case.

## What to leave alone

- `dashboard/functions/api/*.ts` — they're already wired to query the `gold.*` tables that the pipelines will create. No changes needed there once the warehouse catches up.
- `dashboard/public/mocks/*.json` — the contract. Pipelines should match these shapes, not the other way around. Update mocks only if the underlying data model genuinely changes.
- `infrastructure/compose/*` — the platform layer is done. Pipelines run as Dagster assets inside the existing webserver/daemon containers.

## When this is done

The "Post-deploy follow-ups" section of OPERATIONS.md gets shorter. The first follow-up to remove is "VM ClickHouse data migration / repopulation" — that becomes "the pipelines populate gold.* as they run." The `_meta.cached: true` signal on every endpoint flips to `false` and the dashboard renders the user's actual data.
