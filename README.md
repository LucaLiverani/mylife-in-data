# My Life in Data

Personal data platform: collect signals from streaming services (Spotify, YouTube, Google Maps, Google Calendar), warehouse them in ClickHouse, and visualize on a Cloudflare-hosted dashboard.

Canonical docs (in order of precedence):

1. **`IMPLEMENTATION_PLAN.md`** — phase-by-phase build spec; source of truth for what's been built.
2. **`DATA_MODEL.md`** — bronze/silver/gold schemas, MV cascades, gold contracts.
3. **`PIPELINES.md`** — architectural narrative (why bronze→silver→gold, why Redpanda, why dbt).
4. **`OPERATIONS.md`** — running, deploying, debugging the live system.

## Layout

```
ingestion/
  _shared/               clickhouse, redpanda, r2, json_utils, google_oauth
  spotify/               currently-playing producer + history pulls + enrichment
  google/
    portability.py       Data Portability API client (shared by YouTube + Maps)
    maps/                Timeline parser, INSERT helpers, trip segmentation
    youtube/             History parser, Data API v3 enricher
    calendar/            Calendar API client + event parser
orchestration/dagster/   Asset/schedule/sensor definitions + resources
transformations/         dbt project: silver + gold ClickHouse models
warehouse/ddl/           Source-of-truth CREATE TABLEs, applied by apply.sh
infrastructure/          Docker Compose stack + provisioning scripts
dashboard/               React + Vite + Cloudflare Pages Functions
scripts/                 Bootstrap + verify_phase_N + import helpers
exploration/             Jupyter sandbox (not part of the prod path)
```

## Stack

| Service | Purpose | Port |
|---|---|---|
| Redpanda | Kafka-compatible event streaming | 9093 (host) / 9092 (network) |
| ClickHouse | Columnar OLAP warehouse | 8123 (HTTP) / 9200 (native) |
| Dagster | Asset-based orchestration | 3000 |
| Prometheus + Grafana | Monitoring | 9090 / 3001 |
| spotify-current-producer | 5s-poll Spotify producer container | — |

Object storage: Cloudflare R2 (provisioned outside the compose stack). Every credential — ClickHouse, Grafana, Dagster Postgres — flows from `infrastructure/.env` (gitignored), referenced via `${VAR}` in compose YAML. Nothing personal is hardcoded in any committed file.

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

All eight phases (0 → 8) are implemented. See **`IMPLEMENTATION_PLAN.md`** for build details. Each phase has a `scripts/verify_phase_N.py` script you can run to confirm everything's wired up.

Some phases need user-side credentials before they can flow real data:

- **Phase 1+ (Spotify)** — run `ingestion/spotify/authenticate_local.py` once to seed `tokens/.spotify_cache`.
- **Phase 4+ (Google)** — fill `GOOGLE_CLIENT_*` in `infrastructure/.env`, then `scripts/bootstrap_google_auth.py` once.
- **Phase 5 (Maps home anchor)** — `scripts/set_home_location.py` once to seed `silver.maps_home_locations`.

Until then, the dashboard transparently serves `public/mocks/*.json` — every `/api/*` response is tagged `_meta.cached: true` while bronze is empty.

## Production deploy

Live at `https://<PAGES_DOMAIN>` (Cloudflare Pages) talking to a Netcup ARM64 VM through a Cloudflare Tunnel + Access. See **`OPERATIONS.md`** for the full setup, secret-rotation procedures, and common failure modes.
