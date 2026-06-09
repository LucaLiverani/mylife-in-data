# My Life in Data — guide for Claude

Personal data platform: pulls my Spotify / YouTube / Google Maps / Google Calendar
activity into a **ClickHouse** warehouse, models it with **dbt**, orchestrates with
**Dagster**, and serves a **React dashboard on Cloudflare Pages**. This is a **public**
repo, keep it clean and secret-free.

This file is the only doc auto-loaded each session; keep it short. For depth:
- `docs/DATA_MODEL.md` — every bronze/silver/gold table + each gold table → `/api` endpoint.
- `docs/OPERATIONS.md` — run, deploy, debug, credential rotation, common failures.
- `docs/SYNC_TO_VM.md` — laptop ↔ VM sync.

## Architecture — the non-obvious invariants

- **Medallion in ClickHouse**: `bronze` (raw, append-only) → `silver` (cleaned, joined) →
  `gold` (dashboard-ready). The dashboard reads **gold only**.
- **Redpanda streams exactly ONE thing**: the real-time Spotify "now playing" signal
  (`producer → topic spotify.player.current → ClickHouse Kafka-engine table → bronze`).
  **Everything else** (Spotify history, YouTube, Maps, Calendar) is a **scheduled batch
  INSERT** into bronze by Dagster. Redpanda is **not** a general ingestion layer, and
  `start-all.sh` creates only that one topic.
- **dbt vs DDL boundary** (a frequent point of confusion):
  - **dbt models** (`transformations/models/{silver,gold}/*.sql`) are pure SQL **views**.
  - **DDL** (`warehouse/ddl/*.sql`) owns what dbt can't: raw bronze landing tables (dbt
    `sources`), tables filled imperatively by Dagster/LLM/API (`silver.maps_trips*`),
    app-mutable state written by the dashboard (`silver.maps_trip_labels`), and shared
    views needed *before* the dbt run (`silver.maps_activity_keyed`).
  - DDL is **CREATE-only / idempotent**; it never drops. A deleted dbt model leaves an
    orphan view that `deploy.sh` prunes (`warehouse/ddl/prune_orphaned_views.sh`).
- **R2** is object storage for raw provider exports + the nightly warehouse Parquet
  snapshot (`warehouse_r2_archive` job: bronze + non-derivable silver state,
  `archive/warehouse/dt=*`; restore via `scripts/restore_warehouse_from_r2.py`),
  **not** a conveyor in the live pipeline.
- **Orchestration**: Dagster runs producers, sensors, the daily Data Portability ingest,
  and `dbt build` via `dagster-dbt` (~09:00 UTC). **dbt does not run during deploy.**
- **Dashboard**: Cloudflare Pages (static React) + Pages Functions (`dashboard/functions/api/**`)
  query gold over a Cloudflare Tunnel. **Every `/api/*` endpoint falls back to
  `dashboard/public/mocks/*.json`** when the warehouse is down, that's why the UI runs
  offline with no backend, and why mock shapes must track the gold schema.

## Invariants to preserve

- Every **gold** model is queried by a `dashboard/functions/api/**` endpoint or is
  upstream of one. Orphans get pruned on deploy.
- `transformations/models/sources.yml` and `docs/DATA_MODEL.md` must match the **actual**
  bronze tables/DDL. (They drifted once and described fake Kafka topics, verify against
  code, not prose.)
- `dashboard/public/mocks/*.json` shapes must match the gold each endpoint returns.
- Do not reintroduce the legacy Maps Timeline path (`bronze.maps_visits/path/search/directions`,
  `import_maps_timeline_export.py`), removed. Full history comes from the Google Takeout
  importer (`scripts/import_google_takeout.py`).

## Workflow

- **Branch**: work on `dev`; merge to `main` only when clean; never commit directly to `main`.
- **Deploy backend (VM)**: `make deploy-vm` (pushes `dev`, then runs `infrastructure/deploy.sh`
  on the VM: git pull → apply DDL → prune orphaned views → selective container rebuild).
  Then validate: `dagster definitions validate -f orchestration/dagster/definitions.py`.
- **Deploy dashboard**: `cd dashboard && ./scripts/deploy-to-pages.sh` (from the laptop).
- **Local stack**: `cd infrastructure && ./start-all.sh` / `./stop-all.sh` (each walks every
  compose stack: redpanda, clickhouse, dagster, monitoring, umami).
- **Dashboard on mocks** (no backend needed): `cd dashboard && npm install && npm run build
  && npm run pages:dev` → http://localhost:8788 serves `dist/` + Pages Functions, which fall
  back to `public/mocks/`. If 8788 reports "address in use", a previous runtime leaked:
  `fuser -k 8788/tcp`.
- **Visual check**: drive http://localhost:8788 with headless Playwright using
  `reducedMotion: 'reduce'` (page sections sit in scroll-triggered `FadeIn` wrappers and
  screenshot as blank otherwise). Test mobile at 390px width; `scrollWidth > clientWidth`
  on `documentElement` means a horizontal-overflow regression.
- **The laptop has no dbt/dagster CLIs.** `uv run dbt|dagster` fails by design: transforms
  and orchestration only run inside the Dagster container (local stack or VM). dbt views
  rebuild at the ~09:00 UTC Dagster build, **not** on deploy, so a changed gold model goes
  live on the warehouse only at the next build.
- Gotcha: `deploy.sh` git-pulls itself, so a change to *deploy.sh's own logic* only takes
  effect on the next deploy.

## Conventions

- **Public repo**: never commit secrets, IPs, emails, tokens, tunnel IDs. Use placeholders
  (`<VM_IP>`, `<DOMAIN>`, …); real values live in gitignored `ACCESS.md` / `infrastructure/.env`.
- **Env vars**: add to `infrastructure/.env` (empty) and `.env.example` (placeholder)
  together with the code that reads them.
- **LLM endpoint**: provider-neutral OpenAI-compatible (`LLM_API_BASE/_KEY/_MODEL`); never
  name the underlying provider.
- **Prose** (README, docs, content): avoid em dashes.

## Repo map

- `ingestion/` — producers + API clients (Spotify, Google DP/Calendar/YouTube); `_shared/` (clickhouse, r2, llm).
- `orchestration/dagster/` — assets, schedules, sensors, `definitions.py`; `assets/dbt.py` wires dagster-dbt.
- `transformations/` — dbt project (models/, macros/, sources.yml).
- `warehouse/ddl/` — ClickHouse DDL + `apply.sh` + `prune_orphaned_views.sh`.
- `dashboard/` — React app + `functions/api/**` (Pages Functions) + `public/mocks/`.
- `infrastructure/` — docker-compose per service + `start-all.sh` / `deploy.sh`.
- `scripts/` — one-off importers/backfills.
- `private/` — separate PRIVATE nested repo (LinkedIn content); gitignored here.

## Tooling

- `/audit` — check warehouse/dbt/dashboard/doc consistency (orphans, source drift, mock parity).
- `/deploy` — deploy the backend to the VM and validate.
- `reviewer` subagent — repo-tuned code review against the invariants above.
