# My Life in Data — guide for Claude

Personal data platform: pulls my Spotify / YouTube / Google Maps / Google Calendar
activity into a **ClickHouse** warehouse, models it with **dbt**, orchestrates with
**Dagster**, and serves a **React dashboard on Cloudflare Pages**. This is a **public**
repo, keep it clean and secret-free.

This file is the only doc auto-loaded each session; keep it short. For depth:
- `docs/DATA_MODEL.md` — every bronze/silver/gold table + each gold table → `/api` endpoint.
- `docs/OPERATIONS.md` — run, deploy, debug, credential rotation, common failures.
- `docs/DEPLOY.md` — deploy/CI/dev-env design: pains, target flow, migration record.

## Architecture — the non-obvious invariants

- **Medallion in ClickHouse**: `bronze` (raw, append-only) → `silver` (cleaned, joined) →
  `gold` (dashboard-ready). The dashboard reads **gold only**.
- **Redpanda streams exactly ONE thing**: the real-time Spotify "now playing" signal
  (`producer → topic spotify.player.current → ClickHouse Kafka-engine table → bronze`).
  The producer validates each event against a JSON Schema contract
  (`ingestion/spotify/schemas/`, registered in Redpanda's Schema Registry); violations
  route to the dead-letter sibling `spotify.player.current.dlq` →
  `bronze.spotify_player_current_dlq`, never silently dropped. Producer ↔ schema ↔ DDL
  parity is CI-enforced (`scripts/check_stream_contract.py`).
  **Everything else** (Spotify history, YouTube, Maps, Calendar) is a **scheduled batch
  INSERT** into bronze by Dagster. Redpanda is **not** a general ingestion layer, and
  `start-all.sh` creates only that topic and its DLQ.
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
  and `dbt build` via `dagster-dbt` (~09:00 UTC daily safety net). Deploys that touch
  `transformations/` or `warehouse/ddl/` also launch `dbt_build_job` right away.
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

- **Branch**: work on `dev`; never commit directly to `main`. The VM deploys `main`;
  `make deploy-vm` promotes dev→main (fast-forward push) only after CI is green, so
  "merged to main" and "deployable" are the same thing. `main` has required checks
  (`backend-validate`, `dashboard-smoke`, `ddl-idempotency` from `.github/workflows/ci.yml`).
- **Deploy backend (VM)**: `make deploy-vm` (pushes `dev`, waits for the `ci/deployable`
  status, ff-pushes `main`, then runs `infrastructure/deploy.sh` on the VM: validation
  gate → apply DDL → prune orphaned views → selective container recreate → dbt build
  trigger → health checks). `SKIP_CI=1` skips the gate. Design: `docs/DEPLOY.md`.
- **Deploy dashboard**: CI does it automatically on push to `main` when `dashboard/`
  changed (the `deploy-dashboard` job in ci.yml; warn-skips if the `CLOUDFLARE_*` repo
  secrets are absent), so `make deploy-vm` already ships both halves. Manual fallback:
  `make deploy-dashboard` (`--secrets` re-uploads Function secrets, `--preview` targets
  the mocks-backed Pages preview environment).
- **Local stack**: `cd infrastructure && ./start-all.sh` / `./stop-all.sh` (each walks every
  compose stack: redpanda, clickhouse, dagster, monitoring, umami).
- **dbt targets**: `prod` (what Dagster runs; real silver/gold) and `dev` (same warehouse,
  same bronze, views land in `dev_silver`/`dev_gold` via the target-aware
  `generate_schema_name` macro; scoped `dbt_dev` user can't write prod). `make dbt-dev`
  builds dev on the VM (`SELECT='model+'` narrows it); `make dev-clean` resets the
  sandbox; `make dev-hydrate` fills the laptop stack from the R2 snapshot.
- **Dashboard on mocks** (no backend needed): `cd dashboard && npm install && npm run build
  && npm run pages:dev` → http://localhost:8788 serves `dist/` + Pages Functions, which fall
  back to `public/mocks/`. If 8788 reports "address in use", a previous runtime leaked:
  `fuser -k 8788/tcp`.
- **Visual check**: drive http://localhost:8788 with headless Playwright using
  `reducedMotion: 'reduce'` (page sections sit in scroll-triggered `FadeIn` wrappers and
  screenshot as blank otherwise). Test mobile at 390px width; `scrollWidth > clientWidth`
  on `documentElement` means a horizontal-overflow regression.
- **The laptop has no dbt/dagster CLIs.** `uv run dbt|dagster` fails by design: transforms
  and orchestration only run inside the Dagster container (local stack or VM). Deploys
  touching `transformations/` or `warehouse/ddl/` trigger `dbt_build_job` on the VM, so
  deployed models go live within minutes; the ~09:00 UTC build remains the daily net.
- `deploy.sh` re-execs its freshly pulled copy and validates (`dbt parse` +
  `dagster definitions validate` in a throwaway container) before recreating
  anything; on failure it rolls the VM worktree back. A failed deploy is retried
  by just re-running it (`.last_deploy_rev` tracks the last good rev). Design:
  `docs/DEPLOY.md`.

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
