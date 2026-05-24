# Operations

How to run, deploy, and operate the platform. Placeholders like `<VM_IP>`, `<VM_USER>`, `<DOMAIN>`, `<TUNNEL_ID>`, `<CF_ACCESS_CLIENT_ID>`, `<CH_USER>` in this doc stand for personal values — see `PERSONAL.md` (gitignored) for the real ones, or `infrastructure/.env` for what's actually loaded into the running stack.

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
| VM shell | `ssh <VM_USER>@<VM_IP>` | SSH key (`~/.ssh/id_ed25519`) |

---

## Running locally

```bash
cd infrastructure
cp .env.example .env       # then chmod 600 .env and fill in real values
./start-all.sh             # idempotent — boots Redpanda → ClickHouse → Dagster → monitoring
./stop-all.sh
```

| Service | Local URL | Username | Password |
|---|---|---|---|
| Dagster UI | http://localhost:3000 | — | — |
| Redpanda Console | http://localhost:8090 | — | — |
| ClickHouse HTTP | http://localhost:8123 | `<CH_USER>` | (from `infrastructure/.env`) |
| Grafana | http://localhost:3001 | `<CH_USER>` | (from `infrastructure/.env`) |
| Prometheus | http://localhost:9090 | — | — |

If `:3000` is held by another process, uncomment `DAGSTER_PORT=3030` in `infrastructure/.env`.

---

## Deploying the dashboard

The Pages project is **manual deploy** (no GitHub auto-build). Every change ships through `dashboard/scripts/deploy-to-pages.sh`, which (1) builds with vite, (2) uploads every line of `dashboard/.env.production` as a Cloudflare Pages encrypted secret, and (3) `wrangler pages deploy dist`.

```bash
cd dashboard
nvm use 22                   # wrangler 4.x requires Node 22+
./scripts/deploy-to-pages.sh # opens browser for auth if first time
```

`wrangler` is pinned to `4.47.0` because 4.94.0 silently swallows `FunctionsBuildError` messages. If you ever bump it, re-test the deploy in a real terminal.

If you'd rather have pushes to `main` auto-deploy: Cloudflare Pages dashboard → project → **Settings → Builds & deployments → Connect to Git**. Build command `cd dashboard && npm install && npm run build`, output `dashboard/dist`. Then add the same secrets manually under **Environment variables → Production**.

### Production env vars

Six secrets, uploaded automatically by the deploy script from `dashboard/.env.production` (gitignored, 600 perms):

```
CLICKHOUSE_HOST=https://clickhouse.<DOMAIN>
CLICKHOUSE_USER=<CH_USER>
CLICKHOUSE_PASSWORD=<from password manager / infrastructure/.env on VM>
CLICKHOUSE_DATABASE=gold
CF_ACCESS_CLIENT_ID=<CF_ACCESS_CLIENT_ID>
CF_ACCESS_CLIENT_SECRET=<from password manager — shown once at creation>
```

### Mocks vs ClickHouse

Every `/api/*` endpoint tries ClickHouse first; on failure (network, auth, missing table) it falls back to `public/mocks/<path>.json` and tags the response with `_meta.cached: true` (object responses) or `X-Data-Source: cache` (array responses). The Home page shows a "ClickHouse offline" badge when `_meta.cached` is true.

`public/mocks/` is the single source of truth for both dev (`npm run dev` via the Vite plugin in `vite-plugins/mock-api.ts`) and production fallback. Regenerate the seeded sample data with `npm run seed`.

One endpoint (`/api/now/timeline`) is the only remaining mock-only route — Phase 8 turned the rest (`/api/google/calendar`, `/api/system/health`) into real Pages Functions.

---

## VM operations

### Service control

```bash
ssh <VM_USER>@<VM_IP>
cd ~/mylife-in-data/infrastructure
./start-all.sh            # idempotent — brings everything up
./stop-all.sh             # everything down
docker ps                 # 9 containers expected (redpanda + console, clickhouse + keeper, dagster trio, grafana, prometheus)
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
| `PERSONAL.md` (gitignored) | Cheat-sheet mapping every placeholder in this doc to its real value |
| Password manager | Cloudflare service token Client Secret (shown once at creation), VM sudo password, GitHub PAT if used |
| Cloudflare Zero Trust | Service Token `dashboard-clickhouse` (Client ID + Secret), Access app policies |

### Rotating the ClickHouse service token

1. Zero Trust → Access → Service Auth → Service Tokens → `dashboard-clickhouse` → **Rotate**.
2. Save new Client Secret to password manager.
3. Update `dashboard/.env.production` with the new value.
4. Re-deploy: `cd dashboard && nvm use 22 && ./scripts/deploy-to-pages.sh`.

### Rotating the ClickHouse password

1. Edit `infrastructure/.env` on the VM (`CH_ADMIN_PASSWORD=...`).
2. `cd ~/mylife-in-data/infrastructure && ./stop-all.sh && ./start-all.sh`.
3. Update the laptop's `infrastructure/.env` to match (for local-dev parity).
4. Update `dashboard/.env.production`'s `CLICKHOUSE_PASSWORD` and re-deploy.

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

---

## Pipelines

All eight phases of the build are landed (see `IMPLEMENTATION_PLAN.md` for the spec, `git log` for the actual sequence). The Dagster code location loads ~30+ assets across Spotify, Google Maps, YouTube, Calendar, plus observability. dbt builds 40+ silver/gold views on top.

### Weekly Google re-auth

External-user-type apps in Testing mode get refresh tokens that expire after 7 days. Steady-state workflow:

1. The `google_token_health_schedule` (Monday 09:00 UTC) inspects `auth.google_tokens.issued_at` and INSERTs a row in `auth.alerts` when a token is ≥ 6 days old.
2. The dashboard's `/api/system/health` endpoint surfaces these alerts.
3. Open `https://<PAGES_DOMAIN>/api/_internal/google-auth-redirect` in a browser, complete Google's consent screen; the callback writes fresh tokens to `auth.google_tokens`.
4. Dagster reads from `auth.google_tokens` on every resource init — no restart needed.

Long-term escape: apply for OAuth verification (Phase 9) to get permanent refresh tokens. Restricted scopes (Data Portability) additionally require a security assessment.

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
