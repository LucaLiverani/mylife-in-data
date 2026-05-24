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
