---
description: Deploy the backend to the VM and verify it's healthy
allowed-tools: Bash
---

Deploy the backend to the VM, then verify. The VM runs the `main` branch;
`make deploy-vm` fast-forwards `main` to `dev` once CI is green, so deploying
IS the dev→main promotion. The dashboard ships separately (CI deploys it on
push to `main`; manual fallback `dashboard/scripts/deploy-to-pages.sh`).

1. **Pre-flight.** Confirm the working tree is clean and on `dev`. Show
   `git log --oneline origin/main..dev` so I can see exactly what's shipping.
2. **Ship.** Run `make deploy-vm`. It pushes `dev`, waits for the
   `ci/deployable` commit status (escape hatch: `SKIP_CI=1`), fast-forwards
   `main`, then runs `infrastructure/deploy.sh` on the VM: dirty-worktree
   guard → pull + self re-exec → validation gate (dbt parse + dagster
   definitions validate in a throwaway container; rolls back on failure) →
   apply DDL → prune orphaned views → selective container recreate →
   dbt_build_job launch when transformations/DDL changed → health checks.
   If the Dagster image rebuilds (dependency changes only), run the remote
   step detached and wait server-side so a client timeout can't kill a
   half-finished rebuild.
3. **Verify.** deploy.sh already health-checks ClickHouse and the Dagster
   webserver and validates definitions pre-swap; additionally confirm
   `docker ps` shows the stack healthy and, if a dbt build was launched,
   check its run in the Dagster UI.
4. **Report.** Summarize what changed, what restarted, the prune output (any
   orphaned views dropped), and whether a dbt build was triggered.
   Re-confirm a couple of live gold tables are still populated.

Caveats: a failed deploy is safe to retry by re-running `make deploy-vm`
(`.last_deploy_rev` keeps the last good rev as the diff base). Never put
secrets/IPs in committed files (placeholders + `ACCESS.md`). Design doc:
`docs/DEPLOY.md`.
