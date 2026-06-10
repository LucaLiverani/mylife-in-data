# Operations

How to run, deploy, and operate the platform. Placeholders like `<VM_IP>`, `<VM_USER>`, `<DOMAIN>`, `<TUNNEL_ID>`, `<CF_ACCESS_CLIENT_ID>`, `<CH_USER>` in this doc stand for personal values — see `ACCESS.md` (gitignored) for the real ones, or `infrastructure/.env` for what's actually loaded into the running stack.

For the deployment history (what was migrated from Airflow+Kafka to Dagster+Redpanda, how Cloudflare Tunnel + Access were set up), see the brief "Deployment history" section at the bottom.

---

## Live system at a glance

```
                       ┌────────────────────────────────────────────┐
   Browser ─────────►  │  Cloudflare Pages  (<PAGES_DOMAIN>)         │
                       │  React SPA + Workers Functions              │
                       └──────────────┬─────────────────────────────┘
                                      │ POST /?query=…   (CF-Access-Client-Id/Secret headers)
                                      ▼
                       ┌────────────────────────────────────────────┐
                       │  Cloudflare Edge  (Access service token)    │
                       │  clickhouse.<DOMAIN>                        │
                       └──────────────┬─────────────────────────────┘
                                      │ Tunnel (cloudflared)
                                      ▼
                       ┌────────────────────────────────────────────┐
   SSH ──────────────► │  VM  (<VM_USER>@<VM_IP>, arm64)             │
                       │  ─ ClickHouse + Keeper                      │
                       │  ─ Redpanda + Console                       │
                       │  ─ Dagster (webserver + daemon + Postgres)  │
                       │  ─ Prometheus + Grafana                     │
                       │  ─ cloudflared (systemd)                    │
                       └────────────────────────────────────────────┘
```

Only port `22` is open inbound on the VM. Every other service reaches the public internet via the Cloudflare Tunnel.

| Surface | URL | Auth |
|---|---|---|
| Dashboard | `https://<PAGES_DOMAIN>` (custom domain optional) | Public |
| ClickHouse HTTP | `https://clickhouse.<DOMAIN>` | Cloudflare Access **service token** `dashboard-clickhouse` |
| Dagster UI | `https://dagster.<DOMAIN>` | Cloudflare Access email PIN |
| Grafana | `https://grafana.<DOMAIN>` | Cloudflare Access email PIN |
| Redpanda Console | `https://redpanda.<DOMAIN>` | Cloudflare Access email PIN |
| Umami (web analytics) | `https://umami.<DOMAIN>` | Cloudflare Access email PIN; `/script.js` + `/api/send` Bypass (public) |
| VM shell | `ssh <VM_USER>@<VM_IP>` | SSH key (`~/.ssh/id_ed25519`) |

---

## Running locally

```bash
cd infrastructure
cp .env.example .env       # then chmod 600 .env and fill in real values
./start-all.sh             # idempotent — boots Redpanda → ClickHouse → Dagster → monitoring → Umami
./stop-all.sh
```

| Service | Local URL | Username | Password |
|---|---|---|---|
| Dagster UI | http://localhost:3000 | — | — |
| Redpanda Console | http://localhost:8090 | — | — |
| ClickHouse HTTP | http://localhost:8123 | `<CH_USER>` | (from `infrastructure/.env`) |
| Grafana | http://localhost:3001 | `<CH_USER>` | (from `infrastructure/.env`) |
| Prometheus | http://localhost:9090 | — | — |
| Umami | http://localhost:3002 | `admin` | `umami` (change on first login) |

If `:3000` is held by another process, uncomment `DAGSTER_PORT=3030` in `infrastructure/.env`.

---

## Deploying the dashboard

The normal path is CI: a push to `main` that passes all gates deploys the
dashboard automatically (`.github/workflows/ci.yml`, `wrangler pages deploy`
with a Pages-scoped API token). The Pages project itself stays **manual
deploy** (no Pages Git integration; CI does a direct upload).

For emergency deploys, previews, and secret rotation there is the laptop
script:

```bash
cd dashboard
nvm use 22                             # wrangler 4.x requires Node 22+
./scripts/deploy-to-pages.sh           # npm ci + build + deploy to production
./scripts/deploy-to-pages.sh --preview # deploy to the preview environment
                                       # (mocks-backed, no production secrets)
./scripts/deploy-to-pages.sh --secrets # also re-upload .env.production secrets
```

`wrangler` is pinned **exactly** to `4.47.0` in `dashboard/package.json`
(4.94.0+ silently swallows `FunctionsBuildError` messages), and the script runs
`npm ci` first so the lockfile decides the version that executes. If you ever
bump it, verify a deliberately broken Function fails loudly before trusting it,
and re-lock.

### Production env vars

Eight lines in `dashboard/.env.production` (gitignored, 600 perms), uploaded to
the Pages encrypted store only on `deploy-to-pages.sh --secrets` (Pages keeps
previously uploaded secrets, so normal deploys never re-send them). Six runtime
Function secrets plus the two `VITE_UMAMI_*` (build-time, inlined into the
client bundle as the analytics tracker):

```
CLICKHOUSE_HOST=https://clickhouse.<DOMAIN>
CLICKHOUSE_USER=<CH_USER>
CLICKHOUSE_PASSWORD=<from password manager / infrastructure/.env on VM>
CLICKHOUSE_DATABASE=gold
CF_ACCESS_CLIENT_ID=<CF_ACCESS_CLIENT_ID>
CF_ACCESS_CLIENT_SECRET=<from password manager — shown once at creation>
VITE_UMAMI_SRC=https://umami.<DOMAIN>/script.js
VITE_UMAMI_WEBSITE_ID=<from Umami UI → website → Edit>
```

### Mocks vs ClickHouse

Every `/api/*` endpoint tries ClickHouse first; on failure (network, auth, missing table) it falls back to `public/mocks/<path>.json` and tags the response with `_meta.cached: true` (object responses) or `X-Data-Source: cache` (array responses). The Home page shows a "ClickHouse offline" badge when `_meta.cached` is true.

`public/mocks/` is the single source of truth for both dev (`npm run dev` via the Vite plugin in `vite-plugins/mock-api.ts`) and production fallback. Regenerate the seeded sample data with `npm run seed`.

Every `/api/*` route is now a real Pages Function backed by ClickHouse. The last mock-only route, `/api/now/timeline` (the Live Console feed), became a real handler querying `silver.silver_events_unified`; a `_redirects` rewrite to the mock remains only as a dormant fallback (Pages routes the Function ahead of it). Mocks now exist solely as the offline-fallback corpus + dev seed.

---

## Web analytics (Umami)

Cookieless, self-hosted analytics for the dashboard — its own compose stack (`infrastructure/compose/umami/`: `umami` + a dedicated Postgres), host port **3002**, brought up by `start-all.sh` / `deploy.sh` like any other service.

- **Access:** the UI sits behind an email-PIN app, but two extra Access apps **Bypass** (`action: Bypass`, Everyone) `umami.<DOMAIN>/script.js` and `/api/send` so visitors' browsers can load the tracker and post events. Sanity check: `/` → 302 to cloudflareaccess, `/script.js` → 200, `/api/send` (GET) → 405.
- **Tracker** is injected at runtime by `dashboard/src/main.tsx`, gated on `VITE_UMAMI_SRC` + `VITE_UMAMI_WEBSITE_ID` (in `dashboard/.env.production`; unset in dev → dev traffic untracked). Re-deploy the dashboard after changing them.
- **DNS:** the VM has no cloudflared origin cert, so `cloudflared tunnel route dns` fails there — add the `umami` CNAME (→ `<TUNNEL_ID>.cfargotunnel.com`, proxied) via the Cloudflare dashboard instead.

Ingesting Umami events into ClickHouse (`bronze.web_analytics_*` → silver/gold) is a future workstream.

---

## Daily dev cycle (laptop ↔ VM)

The platform runs in two homes. The **VM is canonical production** — runs all
Dagster schedules + sensors, refreshes Google/Spotify tokens, serves the
public dashboard. The **laptop is dev/staging** — code edits + occasional
one-shot experiments. Two env flags keep them coherent:

| Flag | Laptop | VM |
|---|---|---|
| `MYLIFE_TOKEN_WRITER` | `0` | `1` |
| `DAGSTER_SCHEDULES_ENABLED` | `0` | `1` |

`MYLIFE_TOKEN_WRITER` gates `google_oauth.load_and_refresh`'s persist step
(refreshed tokens are still usable in-memory but aren't written back to
ClickHouse). It also gates the `auth.alerts` insert in
`google_token_health`. `DAGSTER_SCHEDULES_ENABLED` gates schedule + sensor
registration in `orchestration/dagster/definitions.py` AND the `producer`
compose profile that runs `spotify-current-producer`. The laptop never
auto-ticks anything; the VM does it all.

### Pushing code laptop → VM

```bash
# from laptop, after editing
make deploy-vm
```

Runs `git push origin dev` then `ssh <VM> 'cd ~/mylife-in-data && ./infrastructure/deploy.sh'`.
`deploy.sh` pulls, reapplies DDL (idempotent), and recreates only the compose
services whose backing files actually changed. Pure docs/scripts/dashboard
edits don't touch any container.

> **dbt is NOT rebuilt by `deploy.sh`.** It applies DDL and reloads the Dagster
> code, but the silver/gold *views* only refresh on the 09:00 UTC
> `dbt_build_schedule` or a manual rebuild. After changing a dbt model, rebuild
> on the VM right away — Dagster UI → Materialize `mylife_dbt_assets`, or
> `ssh <VM> 'docker exec dagster-webserver bash -lc "cd /opt/dagster/repo/transformations && DBT_TARGET_PATH=/tmp/t DBT_LOG_PATH=/tmp/dbt-logs dbt run --profiles-dir ."'` — **after** the pull lands, or the live views silently lag the deployed code. Run the rebuild only once the VM repo is at the new commit (a rebuild against a not-yet-pulled repo builds the old models). Both `DBT_*_PATH` vars redirect dbt's `target/` and `logs/` to writable `/tmp`: the repo is bind-mounted read-only into the container, so without `DBT_LOG_PATH` dbt aborts trying to write `logs/dbt.log`.

`VM_SSH` / `VM_REPO_PATH` come from `infrastructure/.env` (gitignored — see
`ACCESS.md` for real values). `VM_SSH` is anything `ssh` can resolve: a
`~/.ssh/config` alias (recommended — carries the key + port) or a literal
`user@host`. Override on the CLI:

```bash
make deploy-vm VM_SSH=other-alias
```

**The VM pulls over a dedicated GitHub SSH alias.** The VM's git `origin` is
`git@github-mylife-in-data:LucaLiverani/mylife-in-data.git`, a `~/.ssh/config` Host alias
backed by a per-repo deploy key (HostName is still github.com), so it coexists with other
GitHub identities on the box. `deploy.sh` is remote-agnostic (it uses `origin`), so if you
rotate the key or rename the alias, repoint once on the VM:
`git remote set-url origin git@<alias>:LucaLiverani/mylife-in-data.git`. The alias name is in `ACCESS.md`.

### Borrowing tokens for a one-shot laptop run

When the laptop needs to hit Google APIs directly (e.g., re-running a
historical backfill while editing the script), pull the latest tokens from
the VM first:

```bash
make pull-tokens     # or: ./scripts/sync_tokens_from_vm.sh
```

The script reads VM ClickHouse over the existing Cloudflare Tunnel using
the dashboard's service token (`CF_ACCESS_CLIENT_ID` / `CF_ACCESS_CLIENT_SECRET`
in `dashboard/.env.production`), pulls `auth.google_tokens FINAL`, and
INSERTs into the laptop's local ClickHouse. Stale-by-design: laptop tokens
will go bad whenever the VM rotates them — just re-run the script.

**Don't share the Spotify cache.** `tokens/.spotify_cache` is rewritten by
spotipy on every 401; SCPing it mid-flight is race city. Each environment
bootstraps its own Spotify OAuth (`.venv/bin/python ingestion/spotify/authenticate_local.py`
once per host — Spotify issues independent refresh tokens per grant).

### Re-auth flows (Google + Spotify)

| Provider | How |
|---|---|
| Google (either scope group) | Open `https://<PAGES_DOMAIN>/api/internal/google-auth-redirect?group=standard` (or `?group=portability`) on any device → Pages Function writes fresh tokens into VM ClickHouse → next Dagster asset run picks them up. |
| Spotify (VM)   | `ssh <VM> 'cd ~/mylife-in-data && .venv/bin/python ingestion/spotify/authenticate_local.py'` — one-time browser auth; refresh tokens last ~60 days. Run `uv sync` first if `.venv` doesn't exist yet (e.g., right after a fresh bootstrap or before the host venv was added to the provisioning flow). |
| Spotify (laptop) | Same script on the laptop. Cache files don't sync. |

---

## VM operations

### Service control

```bash
ssh <VM_USER>@<VM_IP>
cd ~/mylife-in-data/infrastructure
./start-all.sh            # idempotent — brings everything up
./stop-all.sh             # everything down
docker ps                 # 11 containers expected (redpanda + console, clickhouse + keeper, dagster trio, grafana, prometheus, umami + postgres)
```

The cloudflared tunnel is a systemd service:

```bash
sudo systemctl status cloudflared
sudo systemctl restart cloudflared
sudo journalctl -u cloudflared -n 50 --no-pager
```

### Healthchecks

| What | How |
|---|---|
| Tunnel connectors | `cloudflared tunnel info <TUNNEL_ID>` (run from laptop) → 4 healthy connections to your closest CF edge |
| ClickHouse reachable via tunnel | `curl -I https://clickhouse.<DOMAIN>/ping` → expect 403 (Access blocking anonymous) |
| Dashboard endpoint serving real data | `curl https://<PAGES_DOMAIN>/api/overview/stats \| jq '._meta.cached'` → `false` means live CH, `true` means fallback |
| VM stack | `ssh <VM_USER>@<VM_IP> 'docker ps --format "table {{.Names}}\t{{.Status}}"'` |

### Reinstalling cloudflared on a fresh VM

```bash
# from laptop
scp infrastructure/provisioning/install-cloudflared.sh <VM_USER>@<VM_IP>:~/
scp ~/.cloudflared/<TUNNEL_ID>.json <VM_USER>@<VM_IP>:~/.cloudflared/
scp infrastructure/provisioning/cloudflared-config.example.yml <VM_USER>@<VM_IP>:~/.cloudflared/config.yml
# (edit config.yml to fill in TUNNEL_ID + domain + remove airflow ingress)
ssh -t <VM_USER>@<VM_IP> 'bash ~/install-cloudflared.sh'
```

### Bootstrapping a brand-new VM

See `infrastructure/provisioning/README.md`. Short version: copy `.env.example`, fill in, `source` it, run `bootstrap.sh` on the VM (SSH hardening + Docker), clone the repo, scp `infrastructure/.env`, `./start-all.sh`, then the cloudflared steps above.

---

## Credentials

| Where | What |
|---|---|
| `infrastructure/.env` (laptop + VM, gitignored) | All service passwords. One identity shared by ClickHouse, Grafana, Dagster Postgres |
| `dashboard/.env.production` (gitignored) | Production Pages secrets — synced to Cloudflare encrypted store by `deploy-to-pages.sh` |
| `dashboard/.env.development` (gitignored) | Local-dev CH credentials. Only used by `pages:dev` (rarely; `npm run dev` reads mocks instead) |
| `ACCESS.md` (gitignored) | Cheat-sheet mapping every placeholder in this doc to its real value |
| Password manager | Cloudflare service token Client Secret (shown once at creation), VM sudo password, GitHub PAT if used |
| Cloudflare Zero Trust | Service Token `dashboard-clickhouse` (Client ID + Secret), Access app policies |

### Rotating the ClickHouse service token

1. Zero Trust → Access → Service Auth → Service Tokens → `dashboard-clickhouse` → **Rotate**.
2. Save new Client Secret to password manager.
3. Update `dashboard/.env.production` with the new value.
4. Re-deploy with the secret upload: `cd dashboard && nvm use 22 && ./scripts/deploy-to-pages.sh --secrets`.

### Rotating the ClickHouse password

1. Edit `infrastructure/.env` on the VM (`CLICKHOUSE_PASSWORD=...`).
2. `cd ~/mylife-in-data/infrastructure && ./stop-all.sh && ./start-all.sh`.
3. Update the laptop's `infrastructure/.env` to match (for local-dev parity).
4. Update `dashboard/.env.production`'s `CLICKHOUSE_PASSWORD` and re-deploy
   with `./scripts/deploy-to-pages.sh --secrets`.

---

## Common failures + how to debug

| Symptom | Likely cause | Fix |
|---|---|---|
| Dashboard shows "ClickHouse offline" badge | VM CH down, or auth/network issue | Check `X-Error` header on `/api/overview/stats` for the upstream error |
| `wrangler pages deploy` exits 1 with empty output | wrangler 4.94+ swallows route-build errors | Use `wrangler@4.47.0` (the pinned version); never `npm update wrangler` blindly |
| `cloudflared` runs locally instead of on VM | An old laptop-side daemon is alive | `pkill -f cloudflared` on laptop; the VM systemd service stays up |
| Cloudflare Access app save fails with "allow_authenticate_via_warp cannot be set" | Account-level WARP Session Duration not configured | Zero Trust → Settings → WARP Client → set any duration; retry |
| ClickHouse 4xx error contains "Database gold does not exist" | Phase 2 leftover — no data on VM yet | Expected until pipelines are built. Dashboard falls back to mocks transparently |
| Pages Function returns 200 but `_meta.cached` is `true` | CH is unreachable from the Function OR the query failed | Check `_meta.error` field for the upstream error message |
| Every service's env empty / Postgres `you must specify POSTGRES_PASSWORD` | `infrastructure/.env` got replaced by a broken symlink — it must stay a **regular file** (the `compose/*/.env` symlink *to* it, never the reverse) | Restore it: `scp` the laptop's `infrastructure/.env` to the VM, then re-set `MYLIFE_TOKEN_WRITER=1` + `DAGSTER_SCHEDULES_ENABLED=1` |

---

## Pipelines

The build is complete (see `git log` for the sequence). The Dagster code location loads ~30+ assets across Spotify, Google Maps, YouTube, Calendar, plus observability. dbt builds 40+ silver/gold views on top.

### Pivots from the original plan

Two architectural pivots happened during integration, both forced by Google constraints:

- **Two Google OAuth flows** (`standard` + `portability`). Google rejects mixed-scope consent requests when Data Portability scopes are involved, so each scope group gets its own bootstrap (`scripts/bootstrap_google_auth.py --scope-group {standard|portability}`) and its own row in `auth.google_tokens` keyed by `scope_group`. The `GoogleAuthResource` is registered twice in Dagster (`google_auth_standard` + `google_auth_portability`); assets declare which one they need.

- **Maps is activity-based, not Timeline-based.** Google migrated Timeline (continuous location tracking) on-device only for many accounts in 2024. The pipeline now consumes `myactivity.maps` (search + view + directions) into `bronze.maps_activity` and enriches via Places API into `bronze.maps_place_catalog` (neighborhood + place type). Starred places are ingested as **coordinates only** into `silver.maps_private_places` and used as a spatial exclusion filter (within 100m → `is_private=1` → row never reaches gold tables; friends' home addresses stay private). Full pre-2024 history was loaded once from a Google Takeout export (`scripts/import_google_takeout.py`); there is no ongoing Timeline ingest.

### Where data currently lives

The **VM is the canonical production environment** (cutover 2026-05-26). Bronze ingest, OAuth token refresh, and the spotify-current-producer all run there. The laptop is dev-only (`MYLIFE_TOKEN_WRITER=0`, `DAGSTER_SCHEDULES_ENABLED=0`); use `scripts/sync_tokens_from_vm.sh` if you need to borrow VM tokens for a one-shot local run.

The original cutover procedure is preserved in **`SYNC_TO_VM.md`** as a reference for future fresh-VM builds.

### dbt + the daily auto-loop

`orchestration/dagster/assets/dbt.py` exposes every silver + gold dbt model as a Dagster asset via `dagster-dbt`. The asset module self-bootstraps on Dagster startup:

1. If `transformations/profiles.yml` is missing, copy it from `profiles.yml.example` (all values are env_var()-interpolated, no secrets in the example).
2. If `transformations/target/manifest.json` is missing or older than any `.sql`/`.yml` in `models/` or `macros/`, run `dbt parse` to regenerate.

`dbt_build_schedule` runs `dbt build` daily at 09:00 UTC — after every bronze ingest schedule has run, so silver + gold reflect the freshest data. Default status is `RUNNING`; the toggle persists in Dagster Postgres so a manual stop survives restarts.

Run `dbt build` manually whenever you change a model: in Dagster UI → Lineage → `mylife_dbt_assets` → Materialize. Logs stream into the run page.

### Schedule + sensor defaults

Every schedule and sensor uses `default_status=DefaultScheduleStatus.RUNNING` / `DefaultSensorStatus.RUNNING`. On a fresh VM (or after wiping `dagster-home`), they all come up auto-ticking — no manual UI toggling required. On an existing Dagster instance the defaults are ignored (Postgres state wins), so the first VM bootstrap still needed each toggle flipped once in the UI.

### Warehouse cold archive (R2)

`warehouse_r2_archive_schedule` snapshots the warehouse to R2 as Parquet daily at 05:30 UTC (after the 04:00 Data Portability ingest window):

```
archive/warehouse/dt=YYYY-MM-DD/<database>.<table>.parquet   # zstd, generated by ClickHouse (FORMAT Parquet)
archive/warehouse/dt=YYYY-MM-DD/_MANIFEST.json               # written last = snapshot complete
```

Coverage: **every bronze storage table** (enumerated live from `system.tables`; the Kafka-engine consumer table and view objects are excluded) plus the **non-derivable silver state tables** (`SILVER_STATE_TABLES` in `ingestion/_shared/warehouse_archive.py`: owner trip labels, home anchors, LLM trip verdicts, trip weather, the private-places filter, calendar aliases). Everything else in silver/gold is a dbt view rebuilt by `dbt build`. **Not covered, on purpose**: `auth.*` (OAuth secrets stay out of the archive; recover by re-auth) and `silver.maps_trips` (TRUNCATE+INSERT rebuilt by the 09:30 `maps_trips` job; an additive restore would duplicate its plain-MergeTree rows).

Tables are read with `FINAL` so snapshots are duplicate-free, and uploaded through the existing boto3 helper. No pyarrow/pandas dependency anywhere: ClickHouse produces the Parquet bytes itself. Snapshots older than `R2_ARCHIVE_RETENTION_DAYS` (default 30; 0 = keep forever) are pruned after each successful snapshot. A failed run skips pruning, leaves at most an incomplete `dt=` prefix (no manifest), and alerts through the normal `run_failure_alert_sensor` path.

Restore is additive and idempotent (ReplacingMergeTree dedups against live rows); snapshot files for tables that don't exist on the target (e.g. legacy tables current DDL no longer creates) are skipped with a warning:

```bash
# list available snapshots (also: docker exec dagster-webserver python /opt/dagster/repo/scripts/...)
.venv/bin/python scripts/restore_warehouse_from_r2.py --list
# restore the latest complete snapshot (or --dt YYYY-MM-DD, --table <name> to narrow)
.venv/bin/python scripts/restore_warehouse_from_r2.py
```

Fresh-warehouse recovery order: apply the DDL (`warehouse/ddl/apply.sh`) so the tables exist, restore the snapshot, re-auth Google + Spotify (auth.* is not archived), then run `dbt build` (or wait for the 09:00 UTC build) to refresh silver/gold; `silver.maps_trips` repopulates at the next 09:30 `maps_trips` run.

### Known limitations

- **Google Data Portability 24h cooldown is per OAuth client, not per resource** — and it allows only **one initiate per ~24h**. Maps + YouTube history share a **single** archive: the combined ingest initiates `[myactivity.maps, myactivity.youtube]` in one `initiate_archive` call, then runs Maps place enrichment + YouTube metadata enrichment off the result (this removed the old `maps_daily` 04:00 / `youtube_daily` 04:30 429 collision). Because there's only one initiate per day to spend, **the week is partitioned, all at 04:00 UTC**: `google_dp_daily_schedule` runs the combined activity ingest **Sun + Tue–Sat** (`0 4 * * 0,2,3,4,5,6`), and `maps_private_places_schedule` owns **Monday** (`0 4 * * 1`) for the full-snapshot saved-places refresh (`maps.aliased_places`, `maps.starred_places`), which can't share the time-windowed activity archive. Skipping activity ingest on Mondays is free: Tuesday's run backfills it via the lookback window below. (Previously both ran daily and the 04:00 activity ingest always grabbed the cooldown first, so the Monday 05:00 saved-places sync almost always 429'd and the private-places filter rarely refreshed — the partition fixes that.) The cooldown is anchored to the *last* initiate, so a daily job still lands on its own rolling 24h boundary; anything that perturbs the anchor (a manual re-run, scheduler/container lag) makes the next run briefly race it. Two guards absorb that (see `_initiate_dp_with_cooldown_wait` + `DP_DAILY_LOOKBACK_DAYS` in `assets/google.py`, shared by both schedules): (1) on a time-based 429 the run **sleeps out the cooldown and retries** (same-day recovery), capped at `DP_COOLDOWN_MAX_WAIT_S` (75 min); (2) the activity window is **`DP_DAILY_LOOKBACK_DAYS=3`**, not 1, so if the wait cap is blown (or Monday is skipped) the next success's overlapping window backfills the gap — bronze tables are `ReplacingMergeTree` on natural keys, so overlap dedups for free. The saved-places sync stays **fail-safe**: initiate + wait both happen before the `TRUNCATE`, so a 429/timeout leaves the existing filter intact. **On a 429 failure** you can re-run the job once the cooldown shown in the error (`timestamp_after_24hrs`) has passed — but a manual success re-anchors the cooldown to *that* time, so prefer letting the next scheduled run self-recover.
- **Spotify `/me/player/recently-played` returns at most 50 plays.** `spotify_recently_played_schedule` runs every minute to pull frequently, but if you skip listening for a week the oldest play in `bronze.spotify_plays_raw` won't reach back further than ~50 tracks. No fix — that's the API limit.
- **Spotify saved-tracks pagination caps at 200.** The asset stops after the first page; real libraries can be much larger. Outstanding fix.
- **Spotify "Now playing" shows an idle state when nothing's playing.** The producer emits on track change / play-pause flip (and the current track on startup), polling `current_playback()` with a fallback to `current_user_playing_track()` so it captures playback even when Spotify reports no "active device". When nothing's playing, `bronze.spotify_player_current` simply holds the last transition and the tile reads "the studio is quiet" — the `/api/spotify/current` mock is `no_track`, not a fake track. **Timestamp gotcha:** the producer must emit `captured_at` in ClickHouse's basic `YYYY-MM-DD HH:MM:SS.mmm` form — ISO `…T…Z` strings are silently dropped by the Kafka engine (`kafka_skip_broken_messages=1`), which once left the table permanently empty. Also: `tokens/` is bind-mounted read-only, so spotipy can't persist *refreshed* tokens (harmless repeating "Couldn't write token to cache" warnings) — fine until the refresh token rotates, at which point re-auth on the VM (`authenticate_local.py`).

### Google token lifecycle

The behaviour depends on the GCP app's OAuth consent screen publishing status:

| Publishing status | Refresh-token lifetime | Cadence |
|---|---|---|
| **Testing** (default for unsubmitted apps) | 7 days, hard expiry | Weekly re-auth required. Set `GOOGLE_TOKEN_AGE_ALERT_DAYS=6` in `infrastructure/.env`. |
| **In production** (unverified) | Long-lived for basic + sensitive scopes; restricted scopes (Data Portability) *may* still rotate sooner | Monthly inactivity check. Default `GOOGLE_TOKEN_AGE_ALERT_DAYS=90`. |
| **In production + verified** | Long-lived for all granted scopes (revoked only on password change / 6 months inactive / manual revoke) | Same as above. |

`google_token_health_schedule` runs on the 1st of each month at 09:00 UTC. It inspects `auth.google_tokens.issued_at` and INSERTs a `token_stale` row in `auth.alerts` when older than the threshold. The dashboard's `/api/system/health` surfaces these.

When you do need to re-auth (or want to rotate manually):

1. Open `https://<PAGES_DOMAIN>/api/internal/google-auth-redirect` in a browser.
2. Walk Google's consent screen.
3. The callback writes fresh tokens to `auth.google_tokens`; Dagster picks them up on the next resource init — no restart needed.

If `invalid_grant` starts appearing in Dagster logs for any Google asset, the refresh token has been revoked or expired — re-auth via the link above.

---

## Deployment history (brief)

The platform was migrated from Airflow+Kafka+MinIO to Dagster+Redpanda+ClickHouse on Cloudflare R2, then deployed to an ARM64 VM behind Cloudflare Tunnel + Access. Five phases.

| Phase | Outcome |
|---|---|
| 0 | Verified the legacy local stack worked; inventoried gold tables (snapshot 2026-05-22) |
| 1 | Brought up Dagster + Redpanda locally; shelved Airflow + Kafka (legacy compose dirs later deleted); placeholder Dagster code location |
| 2 | Provisioned a fresh ARM64 VM; SSH-hardened bootstrap; cloned repo; `start-all.sh` brings up 9 containers |
| 3 | Cloudflare Tunnel + Access: 4 hostnames behind email PIN policy (admin UIs) or service-token policy (ClickHouse) |
| 4 | Dashboard Pages Functions rewired to query tunneled ClickHouse; fallback consolidated to a single `public/mocks/` corpus shared by dev plugin and prod Functions |

Notable gotchas (kept here so re-deploys don't relearn the hard way):
- Cloudflare's Zero Trust Application save API rejects requests if account-level **WARP Session Duration** isn't set, even with the WARP toggle off. Fix is in Settings → WARP Client.
- The ClickHouse Access policy must use **action: `Service Auth`** (not `Allow` with a Service Token rule), otherwise the policy validates the token but still requires identity.
- `wrangler@4.94.0` swallows `FunctionsBuildError` messages with no diagnostic output. Stay on `4.47.0` until upstream fixes it.
- `wrangler pages functions build --outfile=dist/_worker.js` writes a multipart-form upload payload, not deployable JS — don't ship `_worker.js` from that command; let `pages deploy dist` build it automatically.
- The original `public/fallback-data/` mechanism never worked in production — `fetch('/relative-path')` throws inside a Worker. The fix lives in `_shared/fallback.ts` (absolute URL via `new URL(..., request.url)`).
