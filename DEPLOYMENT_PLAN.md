# Deployment Plan — Local → Production

> **Memory file.** This is the single source of truth for the local-verify → migrate → deploy work. Edit it as steps complete. Items prefixed `[ ]` are pending; `[x]` are done.

---

## Context

The user provisioned a fresh Debian ARM64 VM (Netcup) following `infrastructure/server/README.md` (SSH hardening only — no Docker, no repo). The local stack is partially up (Kafka, MinIO, Airflow Postgres/Redis are running; ClickHouse, Airflow web/scheduler, monitoring are not). The dashboard at `dashboard/` is deployed on Cloudflare Pages and currently serves 8 of 11 endpoints from a fallback JSON snapshot under `public/fallback-data/` because no live ClickHouse is reachable from Pages.

**Goal:** Have the VM running the full data platform (Dagster + Redpanda + ClickHouse + MinIO), expose ClickHouse via Cloudflare Tunnel with Access service-token gating, and rewire the Cloudflare Pages dashboard to query the tunneled ClickHouse instead of falling back. The dashboard itself stays public; every admin UI sits behind Cloudflare Access email login.

**Decisions locked:**
- Orchestrator: **Dagster** (complete the Airflow → Dagster migration in this plan, then delete Airflow).
- Streaming: **Redpanda** (cut over from Kafka in this plan, then delete the Kafka compose).
- Missing endpoints (`/api/google/calendar`, `/api/system/health`, `/api/now/timeline`): **deferred** — out of scope. The dashboard keeps mock/fallback for those pages.
- Tunnel security: ClickHouse → Cloudflare Access **service token** (no human login, dashboard Functions authenticate via header). All other admin UIs → Cloudflare Access **email policy**. Dashboard host → no Access (public).

---

## Phases

- **Phase 0** — Verify the existing local stack works end-to-end (current Airflow + Kafka baseline).
- **Phase 1** — Migrate locally to Dagster + Redpanda. Tear down Airflow + Kafka.
- **Phase 2** — Deploy the stack to the VM (bootstrap, clone, start).
- **Phase 3** — Cloudflare Tunnel + Access (admin UIs behind email login; ClickHouse behind service token).
- **Phase 4** — Rewire the Cloudflare Pages dashboard to talk to the tunneled ClickHouse.

Stop after any phase if you need a checkpoint — each one leaves the system in a workable state.

---

## Running Locally — quick reference

```bash
cd /home/lliverani/projects/mylife-in-data/infrastructure
./start-all.sh        # boots everything (idempotent)
./stop-all.sh         # stops everything
```

First-time only: each compose dir under `infrastructure/compose/` ships a `.env.example`. Copy each to `.env` and fill in. All credentials are unified — one user, one password — in your local dev:

```bash
for d in infrastructure/compose/*/; do
  [ -f "$d/.env.example" ] && cp "$d/.env.example" "$d/.env" && chmod 600 "$d/.env"
done
# then edit each .env to set the actual password
```

| Service | URL | Username | Password |
|---|---|---|---|
| Dagster UI | http://localhost:3030 | — | — |
| Redpanda Console | http://localhost:8090 | — | — |
| ClickHouse HTTP | http://localhost:8123 | `<REDACTED>` | (your `.env` value) |
| Grafana | http://localhost:3001 | `<REDACTED>` | (your `.env` value) |
| Prometheus | http://localhost:9090 | — | — |

**Repo is committed to a public repo — no plaintext passwords live in any tracked file.** All credentials flow from gitignored `.env` files:
- `infrastructure/compose/clickhouse/.env` — `CH_ADMIN_PASSWORD` (referenced by `users-<REDACTED>.xml` via `<password from_env=...>`)
- `infrastructure/compose/dagster/.env` — Postgres + ClickHouse + R2 creds
- `infrastructure/compose/monitoring/.env` — Grafana admin user/pass
- `dashboard/.env.development` — ClickHouse creds for the local Pages Functions

Dagster runs on **3030** locally because zotify-web-app holds 3000; remove `DAGSTER_PORT=3030` from `infrastructure/compose/dagster/.env` on the VM to get the canonical 3000 back.

---

## Phase 0 — Data verification (Airflow revival skipped)

**Outcome:** ClickHouse has been running historically and all dashboard gold tables are populated through 2026-05-22. **Phase 0.5 row checks already pass.** Airflow Fernet key was lost when re-creating `.env` files, but per user direction we are not reviving Airflow — it gets deleted in Phase 1 anyway. Spotify OAuth re-auth gets folded into Phase 1.4.

### 0.1 Compose `.env` files (done)

- [x] `infrastructure/compose/storage/.env` — MinIO creds + bucket names.
- [x] `infrastructure/compose/clickhouse/.env` — admin user/password, DB, S3 creds.
- [x] `infrastructure/compose/airflow/.env` — kept on disk for reference but Airflow won't be revived.
- [x] `infrastructure/compose/dagster/.env` — Postgres creds, ClickHouse creds. R2 left blank.
- Skipped: `kafka/.env`, `monitoring/.env`, `redpanda/.env` (compose files have no `${VAR}` references).
- Skipped: root `.env` (not consumed by any compose; the docker-compose stack reads from per-service `.env`).

### 0.2 Services brought up

- [x] ClickHouse + Keeper running with existing data volumes (`clickhouse_clickhouse-data`).
- [x] Storage (MinIO) + Kafka still running (don't touch them yet; teardown is Phase 1.7).
- [x] Airflow stack `docker compose down` — its Fernet-encrypted Postgres data is unreadable and we're deleting Airflow anyway.

### 0.3 Data inventory (2026-05-22 snapshot)

| gold table | rows | dashboard endpoint |
|---|---|---|
| `gold_spotify_kpis_summary` | 1 | `/api/spotify/summary` |
| `gold_spotify_top_artists` | 1,730 | `/api/spotify/data` |
| `gold_spotify_genres` | 10 | `/api/spotify/data` |
| `gold_spotify_daily_listening` | 150 | `/api/spotify/data` |
| `gold_spotify_recent_tracks` | 100 | `/api/spotify/recent` |
| `gold_spotify_current_track` | 10M (Kafka engine view) | `/api/spotify/current` |
| `gold_home_daily_data_generation` | 720 | `/api/overview/stats` |
| `gold_home_overview_stats` | 1 | `/api/overview/stats` |
| `gold_home_recent_events` | 30 | `/api/home/recent-events` |
| `gold_youtube_kpis_with_watch_time_dashboard` | 1 | `/api/youtube/data` |
| `gold_maps_kpis_dashboard` | 1 | `/api/travel/data` |

Latest data timestamps: Spotify play 2026-05-22, Maps 2026-05-20, YouTube 2026-05-20. Real-time current-track producer captures still landing every ~1s but `track_name` is blank when nothing is playing — that's expected behaviour, not a bug.

### 0.4 Local dashboard smoke test

- [x] Confirmed dashboard queries against local ClickHouse return real data (curl-tested every endpoint: `/api/spotify/summary` → 1.73k artists, etc.).

**Phase 0 complete.**

---

## Phase 1 — Bring up the new stack locally (no DAG porting)

**User direction:** treat the existing Airflow DAGs as legacy reference, not a porting target. Pipelines get rewritten from scratch later. What matters now is that the new stack spins up cleanly. Only piece worth preserving from the old code is the Spotify OAuth flow.

### 1.1 Redpanda up (done)

- [x] `cd infrastructure/compose/redpanda && docker compose up -d` — broker + console healthy.
- [x] Topics created: `spotify.tracks.raw spotify.player.current spotify.artist_ids spotify.artists.raw google.youtube.raw google.maps.raw` (3 partitions × 1 replica, 7-day retention).
- [x] **Note:** `compression.type=snappy` is rejected by Redpanda in dev-container mode (`INVALID_CONFIG: Unsupported compression type`). Topics created without it; producers can still send snappy-compressed payloads.

### 1.2 Dagster up (done)

- [x] `docker compose build` → `mylife-dagster:latest`.
- [x] Webserver up on **`http://localhost:3030`** (the `.env` overrides `DAGSTER_PORT=3030` because `zotify-web-app-1` occupies `:3000` on this laptop — on the VM, remove that override).
- [x] **Fix applied:** the daemon `command` was missing `-w /opt/dagster/workspace.yaml`; without it Dagster looks for `[tool.dagster]` in `pyproject.toml` and crashloops. Updated in `infrastructure/compose/dagster/docker-compose.yml`.
- [x] Daemon reports all 6 sub-daemons online: AssetDaemon, BackfillDaemon, FreshnessDaemon, QueuedRunCoordinatorDaemon, SchedulerDaemon, SensorDaemon.

### 1.3 Definitions placeholder (done)

`orchestration/dagster/definitions.py` rewritten as a clean starting point. Header documents what to keep (`ingestion/spotify/authenticate_local.py` + the CacheFileHandler pattern) and what gets discarded (Airflow Variables, the BashOperator-driven dbt pattern). One placeholder asset (`placeholder_health_check`) so the code location loads.

### 1.4 Airflow + Kafka shelved (done)

- [x] Airflow stack `docker compose down`.
- [x] Kafka stack `docker compose down`.
- [x] `infrastructure/compose/airflow/` → `infrastructure/compose/_airflow_legacy/`.
- [x] `infrastructure/compose/kafka/` → `infrastructure/compose/_kafka_legacy/`.
- [x] `infrastructure/start-all.sh` rewritten — boots only MinIO → Redpanda → ClickHouse → Dagster → monitoring (5 layers, idempotent).
- [x] Idempotency verified: rerunning `start-all.sh` is a no-op for already-running services.

### 1.5 Deferred until pipelines are rewritten

The items below are the pipeline-rewrite work itself — out of scope for Phase 1 and tracked on the post-deploy list:

- Spotify OAuth: keep `ingestion/spotify/authenticate_local.py` + `get_spotify_producer_client()` from `ingestion/spotify/spotify_api.py`. The CacheFileHandler at `/opt/dagster/dagster_home/.spotify_cache` is the right destination for the new code.
- Producer cutover: when `current_playing_producer.py` (or its rewrite) comes back online, set `KAFKA_BOOTSTRAP_SERVERS=redpanda:9092`. The ClickHouse Kafka engine config in `infrastructure/compose/clickhouse/config/kafka.xml` already references `kafka:9092` and will need a swap to `redpanda:9092` (three occurrences) plus a re-run of `warehouse/ddl/bronze_spotify_current_track_kafka.sql`.
- Fallback JSON refresh: `dashboard/scripts/export-fallback-data.sh` against local ClickHouse — only worth running once new gold tables exist.

**Phase 1 complete = the new stack (Dagster + Redpanda + ClickHouse + MinIO + monitoring) spins up with one command. Existing ClickHouse data is preserved unchanged. Legacy compose dirs renamed `_legacy/`.**

---

## Phase 2 — Deploy the stack to the VM

Follow `infrastructure/provisioning/README.md` as the canonical sequence. Key adaptations below.

### 2.1 Set session variables

```bash
cp infrastructure/provisioning/.env.example infrastructure/provisioning/.env
chmod 600 infrastructure/provisioning/.env
# edit infrastructure/provisioning/.env — fill VM_IP, VM_USER, LOCAL_KEY, GH_REPO, DOMAIN
source infrastructure/provisioning/.env
```

`TUNNEL_ID` stays blank until Phase 3.1 creates the tunnel — re-source `.env` after you fill it in.

### 2.2 Bootstrap

- [ ] `scp infrastructure/provisioning/bootstrap.sh root@$VM_IP:/tmp/`
- [ ] `ssh root@$VM_IP 'bash /tmp/bootstrap.sh'` — installs Docker, UFW, fail2ban, unattended-upgrades. Prints the GitHub deploy key.
- [ ] Add the printed key to GitHub repo → Settings → Deploy keys (read-only).
- [ ] Verify: `ssh $VM_USER@$VM_IP 'whoami && docker --version'`.

### 2.3 Clone the repo + set up `.env`

- [ ] `ssh $VM_USER@$VM_IP "git clone $GH_REPO mylife-in-data"`.
- [ ] Copy the consolidated `infrastructure/.env` from your laptop to the VM:
  ```bash
  scp infrastructure/.env $VM_USER@$VM_IP:mylife-in-data/infrastructure/.env
  ssh $VM_USER@$VM_IP "chmod 600 ~/mylife-in-data/infrastructure/.env"
  ```
- [ ] No need to scp per-service `.env` files — `start-all.sh` recreates the symlinks under each `compose/*/` automatically.

### 2.4 Provision R2 object storage

R2 is a Cloudflare-managed service, not part of compose. Run once on the VM (or wherever you have wrangler authenticated):

- [ ] `ssh $VM_USER@$VM_IP "cd mylife-in-data/infrastructure && ./provisioning/setup-r2.sh"`
- The script creates the bucket via wrangler, prints the dashboard URL for token creation, then writes the four `R2_*` values into `infrastructure/.env` automatically.

### 2.5 Push the Spotify OAuth token

- [ ] `scp .spotipy_token_cache $VM_USER@$VM_IP:~/spotify-tokens/.spotify_cache`.
- [ ] `ssh $VM_USER@$VM_IP "chmod 600 ~/spotify-tokens/.spotify_cache"`.

### 2.6 Start the stack on the VM

- [ ] `ssh $VM_USER@$VM_IP 'cd mylife-in-data/infrastructure && ./start-all.sh'` — first run pulls images (slow on first run).
- [ ] `ssh $VM_USER@$VM_IP 'docker ps --format "table {{.Names}}\t{{.Status}}"'` — every container `(healthy)` or `Up`.

### 2.7 First Dagster materialization on the VM

- [ ] Reach Dagster directly on the VM via SSH tunnel for the initial run: `ssh -L 3000:localhost:3000 $VM_USER@$VM_IP`.
- [ ] Open `http://localhost:3000` on your laptop → manually materialize each asset to seed bronze/silver/gold.
- [ ] Re-run the row-count checks (Phase 0.5) against `curl -s -u admin:... 'http://localhost:8123/?query=...'` proxied through the SSH tunnel.

### 2.8 Pick a strong password on the VM

Local dev uses `<REDACTED>` as the placeholder password (set in your local `.env` files). On the VM:

- [ ] In each `infrastructure/compose/*/.env` on the VM, set `CH_ADMIN_PASSWORD`, `CLICKHOUSE_PASSWORD`, `DAGSTER_POSTGRES_PASSWORD`, `GRAFANA_ADMIN_PASSWORD` to a strong random value (the public-repo-safe pattern means none of these touch git).
- [ ] Same value for ClickHouse + dashboard (so `dashboard/.env.production` consumed by Pages Functions can reach ClickHouse). Different value is fine if you prefer — just align Dagster + dashboard with whatever ClickHouse expects.
- [ ] `./stop-all.sh && ./start-all.sh` to pick up the new envs.

**Phase 2 complete = the platform is producing data on the VM, reachable only via SSH.**

---

## Phase 3 — Cloudflare Tunnel + Access

### 3.1 Create / connect the tunnel

- [ ] Locally: `cloudflared tunnel login`, then `cloudflared tunnel create mylife-data` if you don't already have one.
- [ ] `export TUNNEL_ID=<UUID printed>`.
- [ ] `scp ~/.cloudflared/$TUNNEL_ID.json $VM_USER@$VM_IP:~/.cloudflared/`.
- [ ] `scp infrastructure/provisioning/cloudflared-config.example.yml $VM_USER@$VM_IP:~/.cloudflared/config.yml`.
- [ ] `ssh -t $VM_USER@$VM_IP "sed -i 's/<TUNNEL_ID>/$TUNNEL_ID/g; s/<YOUR_DOMAIN>/$DOMAIN/g' ~/.cloudflared/config.yml"`.
- [ ] Edit the config on the VM to remove the `airflow` ingress (we deleted Airflow in Phase 1). Add nothing for the dashboard — the dashboard lives on Pages, not on this tunnel.

### 3.2 Install `cloudflared` on the VM + route DNS

- [ ] `ssh $VM_USER@$VM_IP "curl -L --output /tmp/cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb && sudo dpkg -i /tmp/cloudflared.deb"`.
- [ ] `ssh $VM_USER@$VM_IP "for h in clickhouse dagster grafana redpanda; do cloudflared tunnel route dns $TUNNEL_ID \$h.$DOMAIN; done"`.
- [ ] `ssh $VM_USER@$VM_IP "sudo cloudflared service install && sudo systemctl enable --now cloudflared"`.
- [ ] Verify: `curl -I https://dagster.$DOMAIN` → expect a 200/302 (or an Access login redirect once 3.4 is done).

### 3.3 Cloudflare Access — email policy for admin UIs

In Cloudflare Zero Trust dashboard for each of `dagster`, `grafana`, `minio`, `redpanda`:

- [ ] **Add an application** → Self-hosted → Application domain: `<service>.<DOMAIN>`.
- [ ] **Policies** → Add policy → Action: Allow. Include: Emails → your address. Save.

### 3.4 Cloudflare Access — service token for ClickHouse

- [ ] Zero Trust → **Access → Service Auth → Service Tokens → Create Service Token**. Name: `dashboard-clickhouse`. Save the Client ID + Client Secret immediately (secret shown once — store in your password manager).
- [ ] Zero Trust → **Access → Applications → Add an application** → Self-hosted. Application domain: `clickhouse.<DOMAIN>`. Leave identity providers blank.
- [ ] **Policies** → Add policy → Action: `Service Auth`. Include: Service Token → `dashboard-clickhouse`. Save.

### 3.5 Verify

- [ ] `curl -i https://clickhouse.$DOMAIN/?query=SELECT+1` → expect 403 from Cloudflare Access (no service-token header).
- [ ] `curl -i -H "CF-Access-Client-Id: <id>" -H "CF-Access-Client-Secret: <secret>" -u <user>:<pw> "https://clickhouse.$DOMAIN/?query=SELECT+1"` → expect `1`.
- [ ] `curl -I https://dagster.$DOMAIN` → expect a Cloudflare Access login page redirect.

**Phase 3 complete = the VM has only port 22 exposed publicly; every other service reaches you via the Cloudflare edge with login or service-token gating.**

---

## Phase 4 — Rewire the dashboard

### 4.1 Extend `clickhouse.ts` + `types.ts` for service-token headers

`dashboard/functions/_shared/types.ts` — add two optional fields:

```ts
export interface Env {
  CLICKHOUSE_HOST: string;
  CLICKHOUSE_USER: string;
  CLICKHOUSE_PASSWORD: string;
  CLICKHOUSE_DATABASE: string;
  CF_ACCESS_CLIENT_ID?: string;       // NEW
  CF_ACCESS_CLIENT_SECRET?: string;   // NEW
  KAFKA_BOOTSTRAP_SERVERS?: string;
  KAFKA_TOPIC?: string;
}
```

`dashboard/functions/_shared/clickhouse.ts` — change the `fetch` headers block (~lines 23-30) to:

```ts
const headers: Record<string, string> = {
  'Authorization': `Basic ${auth}`,
  'Content-Type': 'text/plain',
};
if (env.CF_ACCESS_CLIENT_ID && env.CF_ACCESS_CLIENT_SECRET) {
  headers['CF-Access-Client-Id'] = env.CF_ACCESS_CLIENT_ID;
  headers['CF-Access-Client-Secret'] = env.CF_ACCESS_CLIENT_SECRET;
}
const response = await fetch(url.toString(), { method: 'POST', headers, body: query });
```

- [ ] Make those two edits.
- [ ] Run `npm run build` locally to confirm TS still compiles.

### 4.2 Add Pages secrets

Cloudflare Dashboard → Pages → `mylife-in-data` project → Settings → Environment variables → **Production**:

- [ ] `CLICKHOUSE_HOST` = `https://clickhouse.<DOMAIN>`
- [ ] `CLICKHOUSE_USER` = `admin`
- [ ] `CLICKHOUSE_PASSWORD` = the rotated password from Phase 2.7
- [ ] `CLICKHOUSE_DATABASE` = `gold`
- [ ] `CF_ACCESS_CLIENT_ID` = the Client ID from Phase 3.4
- [ ] `CF_ACCESS_CLIENT_SECRET` = the Client Secret from Phase 3.4

Mark each as **Encrypted**.

### 4.3 Redeploy + verify

- [ ] `cd dashboard && ./scripts/deploy-to-pages.sh` (or push to `main` if you have GitHub auto-deploy hooked up).
- [ ] In a fresh browser tab, open the deployed dashboard URL. Hit every page (Home, Spotify, YouTube, Maps).
- [ ] Open browser devtools → Network → inspect `_meta.cached` in each `/api/*` response — should be `false`. If `true`, the Function fell back; check Cloudflare Pages logs for the upstream error and the service token wiring.

### 4.4 Smoke test the fallback path

Temporarily break the service token (rotate the Client Secret in Cloudflare without updating Pages) and load a page. Expect `_meta.cached === true` and a working (stale) view from the JSON fallback. Restore the secret afterwards.

**Phase 4 complete = the dashboard is live, public, and reads real data from the VM through the Cloudflare-protected tunnel.**

---

## Post-deploy follow-ups (out of scope for this plan but track them)

- ClickHouse nightly backup → MinIO `backups` bucket (eventually R2). A Dagster scheduled asset can run `BACKUP DATABASE gold TO Disk('backups', 'gold_{strftime}.zip')`.
- Migrate MinIO → R2 for object storage. The `cloudflared-config.example.yml` already comments "drop once R2 migration is done" — keep that as the marker.
- Implement the 3 deferred endpoints (`/api/google/calendar`, `/api/system/health`, `/api/now/timeline`) when needed.
- Grafana alert: "no successful Dagster sensor/schedule tick in past 30 min" — Dagster ≥1.8 with `DAGSTER_PROMETHEUS_METRICS_ENABLED=true`.
- Fix the bug in `dashboard/scripts/export-fallback-data.sh`: line 7 reads `CLICKHOUSE_DB`, but the env var passed is `CLICKHOUSE_DATABASE`. Default fallthrough hides it for now.
- The `dbt prod` target in `transformations/profiles.yml` uses ClickHouse native port 9000. Cloudflare Tunnel doesn't tunnel the native protocol; if you ever want to dbt-run from a laptop against the VM, switch the dev target to HTTP 8123.

---

## Rollback notes

- **After Phase 1**: kafka/airflow compose dirs are renamed `_legacy/` — `mv` them back, edit `start-all.sh`, restart.
- **After Phase 2**: VM stack runs but only over SSH — `ssh -L`-tunnel to recover any service. The repo on disk is untouched git-side; `git reset --hard` is always safe.
- **After Phase 3**: `sudo systemctl stop cloudflared` on the VM disables the tunnel; the platform stays up reachable only via SSH.
- **After Phase 4**: revert `clickhouse.ts` + Pages secrets to restore the old fallback-only behaviour. The dashboard never breaks — it always has the static JSON.
