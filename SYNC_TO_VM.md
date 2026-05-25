# Laptop → VM sync plan

The data platform has two homes: your laptop (current dev environment) and the ARM64 VM behind Cloudflare Tunnel + Access (the public dashboard's backend). Right now, everything we've built today lives on the laptop only — the VM stack is provisioned but its ClickHouse is empty. This doc captures the path forward.

## Current state (2026-05-25)

| Thing | Lives on laptop | Lives on VM |
|---|---|---|
| Docker stack (Redpanda + ClickHouse + Dagster + monitoring) | ✅ running | ✅ running (idle) |
| `infrastructure/.env` with real credentials (R2, Google OAuth, Maps API key, webhook secrets) | ✅ filled | ⚠️ stale — placeholders only |
| `auth.google_tokens` (both scope groups) | ✅ seeded by `bootstrap_google_auth.py` | ❌ empty |
| `bronze.*` row counts | spotify=0 (no playback yet), calendar=1,197, youtube_watch=10,480, youtube_search=248, maps_activity=13,697 | all 0 |
| `bronze.maps_place_catalog` | 3 entries (smoke test) | 0 |
| `silver.maps_private_places` | 7 coordinates (from starred places) | 0 |
| Spotify token cache (`tokens/.spotify_cache`) | ✅ | ❌ |
| Pages Functions (5 new ones) | ✅ in repo, not deployed | n/a — they ship to Cloudflare, not the VM |
| Dashboard secrets (`dashboard/.env.production`) | ✅ filled | n/a — uploaded to Cloudflare on deploy |

## Three paths to "public dashboard shows real data"

### Path A — sync laptop state to VM, then deploy Pages (recommended)

Best when you have a free hour and want the cleanest end-state. Assumes the
laptop ↔ VM split flags (`MYLIFE_TOKEN_WRITER`, `DAGSTER_SCHEDULES_ENABLED`)
are already wired through the code (they are — see `OPERATIONS.md` "Daily dev cycle").

1. `scp infrastructure/.env <VM_USER>@<VM_IP>:~/mylife-in-data/infrastructure/.env`
2. **On the VM**, flip the split flags from laptop defaults to prod:
   ```bash
   ssh <VM_USER>@<VM_IP>
   cd ~/mylife-in-data
   sed -i 's/^MYLIFE_TOKEN_WRITER=.*/MYLIFE_TOKEN_WRITER=1/'        infrastructure/.env
   sed -i 's/^DAGSTER_SCHEDULES_ENABLED=.*/DAGSTER_SCHEDULES_ENABLED=1/' infrastructure/.env
   ```
3. On VM: `git pull origin dev` (picks up the gating code + `deploy.sh` + the `producer` compose profile).
4. On VM: `./infrastructure/start-all.sh` — idempotent. With `DAGSTER_SCHEDULES_ENABLED=1` it activates the `producer` profile so `spotify-current-producer` boots.
5. On VM: `set -a; source infrastructure/.env; set +a; CLICKHOUSE_DDL_HOST=localhost bash warehouse/ddl/apply.sh` (idempotent).
6. Copy Google token rows from laptop to VM (the OAuth bootstrap script wants a browser on the host that ran it; copying rows is simpler):
   ```bash
   # On laptop:
   docker exec clickhouse clickhouse-client --user <REDACTED> --password <REDACTED> \
     --query "SELECT * FROM auth.google_tokens FINAL FORMAT JSONEachRow" > /tmp/google_tokens.jsonl
   scp /tmp/google_tokens.jsonl <VM_USER>@<VM_IP>:/tmp/
   # On VM:
   docker exec -i clickhouse clickhouse-client --user <REDACTED> --password <REDACTED> \
     --query "INSERT INTO auth.google_tokens FORMAT JSONEachRow" < /tmp/google_tokens.jsonl
   ```
7. On VM, bootstrap a VM-local Spotify cache (one-time browser auth on the VM; Spotify allows independent grants per host, so the laptop's cache stays valid too):
   ```bash
   cd ~/mylife-in-data && python ingestion/spotify/authenticate_local.py
   ```
8. On VM, re-run the historical backfills (Calendar pull, YouTube DP, Maps activity ingest) using the same direct-Python scripts you used on the laptop. **Don't** `rsync` bronze data — re-running gives clean dedup state.
9. On VM, kick off Maps Places API enrichment (will eat ~$45 of the $200 monthly free credit).
10. **On laptop**, `cd dashboard && nvm use 22 && ./scripts/deploy-to-pages.sh` to ship the Pages Functions + secrets.
11. From the Dagster UI on the VM, trigger `calendar_channels_setup` to switch Calendar from polling → webhook-driven (the webhook URL `https://<PAGES_HOST>/api/internal/calendar-webhook` is now live).

From now on, day-to-day code changes ship via `make deploy-vm` on the laptop
(see `OPERATIONS.md` → "Daily dev cycle").

### Path B — deploy Pages for auth-flows only

Best when you specifically want the re-auth link working *before* doing the full sync (e.g., to renew tokens from anywhere while you're not at your laptop). Dashboard tiles will keep showing mocks until Path A is done.

1. `cd dashboard && nvm use 22 && ./scripts/deploy-to-pages.sh`
2. Test: visit `https://<PAGES_HOST>/api/internal/google-auth-redirect?group=standard` in a browser → walks OAuth → token lands in **VM** ClickHouse (which is what `CLICKHOUSE_HOST` in `dashboard/.env.production` points at).

The calendar webhook would technically also work end-to-end after deploy (Google → Pages → VM ClickHouse → idle Dagster on VM), but until you do Path A the Dagster sensor on the VM can't drain notifications into events because there's no `auth.calendar_channels` row to look up calendar IDs from.

### Path C — tunnel laptop ClickHouse to Cloudflare (not recommended)

Set up a temporary Cloudflare tunnel pointing at your laptop's ClickHouse, swap `CLICKHOUSE_HOST` in `dashboard/.env.production` to that tunnel hostname, deploy. Real data appears on the public dashboard while you're still ingesting locally. Fragile: laptop must be on, tunnel running, and the public domain now leaks your laptop's network state.

## My recommendation

**Path A**, in one focused session. Until then, the laptop stack is fully functional for development and you can keep iterating on dbt models, Dagster assets, and the Maps activity inference layer without needing the VM at all. When you're ready to publish, do the sync.

## Open follow-ups (not blocking)

- Maps Places API enrichment full loop (~2,650 lookups, ~$45 of $200 free credit). One-shot once on whichever environment you decide is canonical (laptop or VM).
- Monthly Timeline export (manual phone export → `scripts/import_maps_timeline_export.py`) for ground-truth visit data that `silver.maps_trips` and trip segmentation can consume.
- Inference layer (heuristic country/city from activity density, deferred ML model trained on Timeline ground truth) — Phase 5c, build when you have ≥1 month of Timeline exports as labels.
