---
description: Deploy the backend to the VM and verify it's healthy
allowed-tools: Bash
---

Deploy the backend to the VM, then verify. The VM runs the `dev` branch; the dashboard
deploys separately (`dashboard/scripts/deploy-to-pages.sh`) and is not part of this.

1. **Pre-flight.** Confirm the working tree is clean and on `dev`. Show
   `git log --oneline origin/dev..dev` so I can see exactly what's shipping.
2. **Ship.** Run `make deploy-vm` (reads `VM_SSH` / `VM_REPO_PATH` from `infrastructure/.env`;
   it pushes `dev` then runs `infrastructure/deploy.sh` on the VM: git pull → apply DDL →
   prune orphaned views → selective container rebuild). If the Dagster image rebuilds, run
   the remote step detached and wait server-side so a client timeout can't kill a
   half-finished rebuild.
3. **Verify.** In the `dagster-daemon` container run
   `dagster definitions validate -f orchestration/dagster/definitions.py` and confirm
   "all code locations passed". Check `docker ps` shows the stack healthy.
4. **Report.** Summarize what changed, what restarted, and the prune output (any orphaned
   views dropped). Re-confirm a couple of live gold tables are still populated.

Caveats: `deploy.sh` updates itself on pull, so a change to deploy.sh's own logic won't run
until the next deploy. Never put secrets/IPs in committed files (placeholders + `ACCESS.md`).
