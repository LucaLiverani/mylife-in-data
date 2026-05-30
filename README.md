# My Life in Data

Personal data platform: collect signals from streaming services (Spotify, YouTube, Google Maps, Google Calendar), warehouse them in ClickHouse, and visualize on a Cloudflare-hosted dashboard.

Canonical docs:

1. **`OPERATIONS.md`** — running, deploying, and debugging the live system. Start here.
2. **`DATA_MODEL.md`** — bronze/silver/gold schemas and the gold→dashboard contract.
3. **`SYNC_TO_VM.md`** — the laptop ↔ VM split and the original cutover (kept as a fresh-VM reference).

## Layout

```
ingestion/
  _shared/               clickhouse, redpanda, r2, json_utils, google_oauth
  spotify/               currently-playing producer + history pulls + enrichment
  google/
    portability.py       Data Portability API client (shared by YouTube + Maps)
    maps/                Activity parser + Places API client + Timeline import
    youtube/             History parser + Data API v3 enricher
    calendar/            Calendar API client + event parser
orchestration/dagster/   Asset/schedule/sensor definitions + resources
transformations/         dbt project: silver + gold ClickHouse models
warehouse/ddl/           Source-of-truth CREATE TABLEs, applied by apply.sh
infrastructure/          Docker Compose stack + provisioning scripts
dashboard/               React + Vite + Cloudflare Pages Functions
scripts/                 Google/Spotify auth bootstrap, Maps Timeline import, connection probes
```

## Stack

| Service | Purpose | Port |
|---|---|---|
| Redpanda | Kafka-compatible event streaming | 9093 (host) / 9092 (network) |
| ClickHouse | Columnar OLAP warehouse | 8123 (HTTP) / 9200 (native) |
| Dagster | Asset-based orchestration | 3000 |
| Prometheus + Grafana | Monitoring | 9090 / 3001 |
| spotify-current-producer | 5s-poll Spotify producer container | — |

Object storage: Cloudflare R2 (provisioned outside the compose stack). Every credential — ClickHouse, Grafana, Dagster Postgres, Google OAuth, R2 keys, Maps API — flows from `infrastructure/.env` (gitignored), referenced via `${VAR}` in compose YAML. Nothing personal is hardcoded in any committed file.

Python deps: managed with **uv** (`pyproject.toml` + `uv.lock`). `uv sync` recreates the venv.

## Quick start (local)

```bash
cd infrastructure
cp .env.example .env       # then chmod 600 .env and fill in real values
./start-all.sh
```

URLs printed at the end. The stack uses one identity across every service — username + password come from `infrastructure/.env`.

```bash
./stop-all.sh
```

## Pipelines status

The full ingest → transform → serve loop is live: Dagster loads ~30 assets across Spotify, YouTube, Maps, and Calendar, and dbt builds the silver + gold ClickHouse views the dashboard reads. Two pivots from the original design, both forced by Google API constraints:

- **Two Google OAuth flows** (`standard` + `portability`). Google rejects mixed-scope consent requests for Data Portability scopes, so each scope group gets its own bootstrap + its own row in `auth.google_tokens`.
- **Maps is activity-based, not Timeline-based**. Google's 2024 migration moved Timeline (continuous location tracking) on-device only for many accounts. The pipeline now consumes `myactivity.maps` (search + view + directions, ~5MB/day) and enriches via Places API (neighborhood + place type). Timeline data flows in only via monthly manual phone export → `scripts/import_maps_timeline_export.py`. Starred places are ingested as **coordinates only** and used as a spatial exclusion filter so friends' home addresses never reach the public dashboard.

Setup gates that require user action before data flows:

- **Spotify** — run `.venv/bin/python ingestion/spotify/authenticate_local.py` once per host to seed `tokens/.spotify_cache`. The `spotify-current-producer` container starts automatically via `start-all.sh` when `DAGSTER_SCHEDULES_ENABLED=1` (VM-only by default).
- **Google** — fill `GOOGLE_CLIENT_*` + `GOOGLE_MAPS_API_KEY` in `infrastructure/.env`. For the first-time bootstrap, either run `scripts/bootstrap_google_auth.py` locally or use the Pages re-auth flow (`https://<PAGES_DOMAIN>/api/internal/google-auth-redirect?group={standard,portability}`) which writes tokens directly into VM ClickHouse over the Cloudflare Tunnel.
- **R2** — fill the 5 `R2_*` keys in `infrastructure/.env`; smoke-test with `scripts/test_r2_connection.py`.
- **Maps home anchor** (optional, for trip segmentation) — `scripts/set_home_location.py`.

Connection probes for fast diagnostics during setup: `scripts/test_r2_connection.py`, `scripts/test_google_connection.py`, `scripts/probe_maps_data_portability.py`.

Until each gate is done, the dashboard transparently serves `public/mocks/*.json` — every `/api/*` response is tagged `_meta.cached: true`.

## Production deploy

Live at `https://<PAGES_DOMAIN>` (Cloudflare Pages) talking to an ARM64 VM through a Cloudflare Tunnel + Access. The VM owns OAuth-token refresh and runs every scheduled ingest; the laptop is dev-only (`DAGSTER_SCHEDULES_ENABLED=0`, `MYLIFE_TOKEN_WRITER=0` — see `OPERATIONS.md` → "Daily dev cycle").

Daily auto-loop:
```
bronze ingest (Spotify recently-played every 1m, combined Maps+YouTube Data Portability 04:00,
               Calendar webhook + daily channel renew, freshness monitor 08:00)
  → dbt build (silver + gold rebuild at 09:00 UTC)
  → public dashboard serves live ClickHouse data
```

See **`OPERATIONS.md`** for setup, secret rotation, and common failure modes. **`SYNC_TO_VM.md`** documents the original laptop→VM cutover (already executed; kept as a reference for future fresh-VM builds).
