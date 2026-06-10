# Deploy design: pains, target flow, migration

Design doc for the deploy hardening + CI + dev environment work (June 2026).
Written before the changes, kept as the migration tracker and the rationale
record. Operational how-to lives in `docs/OPERATIONS.md`; this file explains
*why* the deploy works the way it does.

## Pain points this redesign fixes

All verified against code before changing anything:

1. **deploy.sh self-update staleness.** The script git-pulls the repo (including
   itself) mid-run and keeps executing the pre-pull copy, so changes to deploy
   logic only took effect on the *next* deploy.
2. **Retry no-op after a mid-deploy failure** (worse than 1, found during the
   audit). A failed deploy left HEAD already advanced; rerunning deploy.sh saw
   `BEFORE == AFTER` and exited 0 with "nothing to deploy" while containers were
   stale. Recovery required manually passing the old rev as `$1`.
3. **No validation before container recreation.** A commit with a broken
   `definitions.py` was force-recreated straight into production; the
   `dagster definitions validate` step was manual and post-hoc. Worse, the repo
   is bind-mounted read-only into the running containers, so unvalidated pulled
   code was live on their filesystem the moment the pull completed.
4. **Deployed code != applied transforms.** Deploy applied DDL but dbt views
   only rebuilt at the 09:00 UTC Dagster schedule, so a changed gold model
   lagged up to ~24h behind the deployed SQL.
5. **Split deploys, easy to ship one half.** Backend via `deploy.sh` on the VM,
   dashboard via `deploy-to-pages.sh` from the laptop, nothing connected them.
6. **The wrangler "pin" was fictional.** Docs mandated `4.47.0` (4.94+ silently
   swallows `FunctionsBuildError`), but `package.json` declared `^4.47.0` and
   the lockfile had resolved 4.99.0, inside the documented-bad range.
7. **Stateful VM worktree.** `git pull --ff-only` under `set -e` aborted every
   deploy on any stray VM-side edit, with no diagnostic.
8. **Over-broad rebuilds.** Any `orchestration/`/`ingestion/`/`transformations/`
   change triggered a full Dagster image rebuild, although that code is
   bind-mounted and only dependency changes actually need `--build`.
9. **Production ran the `dev` branch.** Every push to dev was one ssh away from
   production, and branch protection on `main` would have gated nothing.

## Target flow

### CI (GitHub-hosted runners, zero secrets)

`.github/workflows/ci.yml`, on push to `dev`/`main` and PRs to `main`. No
secrets exist in CI at all, so fork PRs are safe by construction. Three gates:

- **backend-validate**: `dbt parse` (its own failing step), then
  `dagster definitions validate`. Both proven to run offline with no services
  and no credentials. **Load-bearing invariant**: `dagster definitions
  validate` exits 0 even when a dbt model is broken, because the import-time
  bootstrap in `orchestration/dagster/assets/dbt.py` catches the parse failure
  and silently drops all dbt assets. The separate `dbt parse` step IS the dbt
  gate; never fold it away.
- **dashboard-smoke**: `npm ci`, build, mock-generator drift check
  (`npm run seed` + clean diff), then a Playwright smoke against the
  mocks-backed `pages:dev` server: every `/api/*` returns 200 with
  `X-Data-Source: cache`, render with `reducedMotion: 'reduce'`, no horizontal
  overflow at 390px.
- **ddl-idempotency**: run `warehouse/ddl/apply.sh` twice against a throwaway
  ClickHouse service container (same major as prod). Proves the CREATE-only /
  idempotent DDL invariant mechanically.

On push, a final job posts a classic commit status `ci/deployable` that the
deploy tooling gates on (raw check-runs queries pass vacuously in the seconds
after a push, before any runs are created; the explicit status does not).

### CD, backend (manual trigger, hardened script)

Production deploys from **`main`**. `dev` stays the working branch; shipping is
a fast-forward push of the same SHA (`git push origin dev:main`), which branch
protection allows because the required checks already passed on that commit.

`make deploy-vm` = push dev, wait for `ci/deployable` (escape hatch:
`SKIP_CI=1`), ff-push to main, then ssh + `infrastructure/deploy.sh`. The
script's order:

1. Dirty-worktree guard (fail loudly with the offending paths).
2. Resolve `BEFORE` from `$1`, else the `.last_deploy_rev` state file, else
   HEAD. The state file is written only as the final step of a *successful*
   deploy, so a failed deploy retries from the last good rev instead of
   no-opping.
3. Fetch + checkout + `pull --ff-only origin main`; if HEAD moved, re-exec the
   freshly pulled script (`DEPLOY_REEXEC` guard) so new deploy logic applies to
   the deploy that ships it.
4. Build the Dagster image only if dependencies changed (Dockerfile,
   `pyproject.toml`, `uv.lock`, `requirements*`); code-only changes are
   bind-mounted and need recreation, not a rebuild.
5. **Validation gate** in a throwaway `--network none` container from the
   image about to be deployed: `dbt parse`, then `dagster definitions
   validate`. On failure: `git reset --hard $BEFORE` (the bind mount means
   broken code on disk would go live on any container restart) and exit
   non-zero.
6. Apply DDL (idempotent, CREATE-only) + prune orphaned dbt views.
7. Selective recreation per changed paths, as before.
8. If `transformations/` or `warehouse/ddl/` changed and
   `DAGSTER_SCHEDULES_ENABLED=1`: launch `dbt_build_job` via the Dagster CLI in
   the webserver container, so deployed models are live in minutes, not at
   09:00 UTC. (The job only exists when schedules are enabled.)
9. Health checks (ClickHouse ping, Dagster server info), remind about the
   dashboard half if `dashboard/` changed, write `.last_deploy_rev`.

`dagster.yaml` is bind-mounted over the named-volume path in the compose file,
so instance-config changes deploy normally (previously the `dagster-home`
volume shadowed the image-baked copy and required a manual `docker cp`).

Deliberate non-goals: no self-hosted runner (GitHub advises against them on
public repos and the VM holds personal data), no k8s/GitOps, and the VM-side
auto-deploy poller is deferred until the gates have soaked under manual
triggering.

### CD, dashboard (GitHub Actions)

A deploy job in the same workflow ships `dashboard/` on push to `main` once all
three gates pass, via `wrangler pages deploy` with a Pages-scoped
`CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` (the only secrets in the
system, and they cannot reach the VM). Runtime Function secrets live in the
Pages project settings and are no longer re-uploaded per deploy.
`dashboard/scripts/deploy-to-pages.sh` remains the documented emergency manual
path (with the wrangler version actually pinned, `npm ci` first, and a
`--secrets` flag for the rare rotation; `--preview` deploys to the Pages
preview environment instead of production).

### Dev environment

Two tiers, matching the two kinds of change:

- **Tier 1, new models / gold / dashboard pages** (the common case): `dev`
  dbt target on the production warehouse. `generate_schema_name` prefixes
  non-prod targets, so `dbt build --target dev` lands every view in
  `dev_silver` / `dev_gold` while `source()` keeps resolving to the literal
  `bronze` database: dev reads the same already-ingested bronze with zero
  copying and zero new auth. A scoped `dbt_dev` ClickHouse user (SELECT on
  prod layers, full rights only on `dev_*`, nothing on `auth.*`) makes a
  wrong-target run physically unable to clobber prod. Note `dbt_dev` is a
  write-safety boundary, not a confidentiality one: SELECT on bronze is
  SELECT on the full personal history.
- **Tier 2, new ingestion sources**: the laptop compose stack (identical to
  the VM, inert via `DAGSTER_SCHEDULES_ENABLED=0` / `MYLIFE_TOKEN_WRITER=0`),
  hydrated from the nightly R2 Parquet snapshots with
  `scripts/restore_warehouse_from_r2.py` (R2 keys only, no provider OAuth).
  Google tokens can be borrowed read-only with `make pull-tokens`; Spotify is
  a per-host grant via `ingestion/spotify/authenticate_local.py`. Never run
  the calendar watch assets outside prod (channel registrations point at the
  production webhook).

A second full stack on the VM is explicitly rejected: hardcoded container
names, one shared docker network, unparameterized ports, and unverified RAM
headroom.

### Invariants worth re-stating

- `dbt parse` must stay a separate failing step everywhere `dagster
  definitions validate` is used as a gate (see backend-validate above).
- The dbt profile's `prod` output is what Dagster runs; the `dev` output
  prefixes databases via the macro. The rename from the old single output
  (confusingly named `dev`) had to be atomic with the macro change and the
  Dagster target pin; after touching any of these, verify the next scheduled
  09:00 UTC build still lands in unprefixed `silver`/`gold`.
- DDL stays CREATE-only; users/grants cannot be committed as DDL in a public
  repo, hence `warehouse/ddl/bootstrap_dev_user.sh` reads the password from
  env at runtime.
- Every dbt model is a view. The "dev costs nothing" and "rebuild is the
  rollback" reasoning depends on that; revisit this doc if a model ever
  becomes `table`/`incremental`.

## Migration checklist

- [x] Step 1: pin wrangler exactly, harden `deploy-to-pages.sh` (`npm ci`,
      clean-tree check, `--secrets` flag, `--preview` mode), fix OPERATIONS.md.
- [x] Step 2: harden `infrastructure/deploy.sh` (state file, re-exec,
      validation gate, rebuild split, dbt trigger, health checks) +
      `dagster.yaml` bind-mount.
- [x] Step 3: `.github/workflows/ci.yml` (backend-validate, dashboard-smoke,
      ddl-idempotency, `ci/deployable` status) + `dashboard/scripts/smoke.mjs`;
      green on dev and main.
- [x] Step 4: flip deploys to `main` (deploy.sh + Makefile gate + ff-push),
      branch protection requiring the three checks (live, verified by the
      first protected ff-push).
- [x] Step 5: dev dbt target + `dbt_dev` user + `dev_silver`/`dev_gold` DDL +
      `make dbt-dev` / `dev-clean` / `dev-hydrate`. Verified against the local
      stack: full dev build as `dbt_dev`, prod writes and `auth.*` reads
      ACCESS_DENIED.
- [x] Step 6: Pages CD job (warn-skips until `CLOUDFLARE_API_TOKEN` /
      `CLOUDFLARE_ACCOUNT_ID` repo secrets exist).
- [ ] Add the two Cloudflare repo secrets so Pages CD goes live.
- [ ] VM execution: deploy, bootstrap `dbt_dev` (password generated on the VM,
      `CLICKHOUSE_DBT_DEV_*` in the VM's `.env`), verify gate + dbt trigger +
      bind-mount + dev builds end to end.
- [ ] Watch the first post-rename 09:00 UTC build land unprefixed (mandatory).

## Known gaps (accepted, tracked in TODO)

- No disk-full story on the VM (image GC after repeated `--build`, ENOSPC
  behavior of the nightly archive).
- No rollback runbook for validated-but-runtime-bad deploys; DDL is
  forward-only by design.
- Workers free-tier budget (~100k req/day) is shared by prod and previews;
  on exhaustion the mocks fallback dies too (it runs inside the Function).
- No continuous "is prod serving live, not silently mocks" probe; the
  `X-Data-Source` header is the ready-made oracle for the monitoring stack.
