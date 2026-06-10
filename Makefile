# Convenience targets for the laptop ↔ VM workflow.
# See docs/OPERATIONS.md "Daily dev cycle" for the full picture.

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help

ENV_FILE := infrastructure/.env

# Read VM SSH endpoint from infrastructure/.env (gitignored). VM_SSH accepts
# anything ssh can resolve: a config alias like `perry` (recommended; pulls
# user/host/key from ~/.ssh/config) or a plain `user@host`.
# Override on the CLI: `make deploy-vm VM_SSH=other-alias`.
VM_SSH       ?= $(shell grep -E '^VM_SSH='       $(ENV_FILE) 2>/dev/null | head -n1 | cut -d= -f2-)
VM_REPO_PATH ?= $(shell grep -E '^VM_REPO_PATH=' $(ENV_FILE) 2>/dev/null | head -n1 | cut -d= -f2-)
VM_REPO_PATH := $(if $(VM_REPO_PATH),$(VM_REPO_PATH),~/mylife-in-data)
GH_REPO      ?= $(shell git remote get-url origin | sed -E 's#.*github.com[:/]##; s#\.git$$##')

.PHONY: help deploy-vm ci-gate deploy-dashboard pull-tokens vm-status vm-logs-dagster

help:
	@echo "mylife-in-data — workflow targets"
	@echo
	@echo "  make deploy-vm        Push dev, wait for CI, ff-push main, deploy on the VM."
	@echo "                        (SKIP_CI=1 skips the gate; admin push bypasses protection.)"
	@echo "  make deploy-dashboard Manual dashboard deploy from the laptop (CI does it on main)."
	@echo "  make pull-tokens      Copy Google OAuth tokens from VM → laptop ClickHouse."
	@echo "  make vm-status        Show docker ps on the VM."
	@echo "  make vm-logs-dagster  Tail dagster-webserver logs on the VM."
	@echo
	@echo "VM endpoint comes from $(ENV_FILE) (VM_SSH = ssh alias or user@host,"
	@echo "VM_REPO_PATH = path on VM). Override on the CLI: make deploy-vm VM_SSH=other"

# Wait for the ci/deployable classic commit status that ci.yml posts on push.
# Raw check-runs queries pass vacuously right after a push (before any runs
# exist); this explicit status only exists once every gate succeeded.
ci-gate:
	@if [ "$(SKIP_CI)" = "1" ]; then \
	    echo "⚠ SKIP_CI=1 — skipping the ci/deployable gate."; \
	else \
	    sha=$$(git rev-parse dev); \
	    echo "→ Waiting for ci/deployable on $$sha (up to 10 min)..."; \
	    for i in $$(seq 1 60); do \
	        state=$$(gh api repos/$(GH_REPO)/commits/$$sha/status \
	            --jq '[.statuses[] | select(.context=="ci/deployable")][0].state' 2>/dev/null); \
	        if [ "$$state" = "success" ]; then echo "✓ CI green."; exit 0; fi; \
	        sleep 10; \
	    done; \
	    echo "✗ ci/deployable never turned green (last state: $${state:-none})."; \
	    echo "  Check: gh run list --branch dev    (escape hatch: SKIP_CI=1)"; \
	    exit 1; \
	fi

deploy-vm:
	@if [ -z "$(VM_SSH)" ]; then \
	    echo "ERROR: VM_SSH must be set in $(ENV_FILE) (ssh alias like 'perry' or 'user@host')."; \
	    exit 1; \
	fi
	@echo "→ Pushing dev branch to GitHub..."
	git push origin dev
	@$(MAKE) --no-print-directory ci-gate
	@echo "→ Fast-forwarding main to dev (same SHA, checks already green)..."
	git push origin dev:main
	@echo "→ Triggering deploy on $(VM_SSH):$(VM_REPO_PATH)..."
	ssh $(VM_SSH) 'cd $(VM_REPO_PATH) && ./infrastructure/deploy.sh'

deploy-dashboard:
	cd dashboard && ./scripts/deploy-to-pages.sh

pull-tokens:
	./scripts/sync_tokens_from_vm.sh

vm-status:
	@if [ -z "$(VM_SSH)" ]; then \
	    echo "ERROR: VM_SSH must be set in $(ENV_FILE)."; \
	    exit 1; \
	fi
	ssh $(VM_SSH) 'docker ps --format "table {{.Names}}\t{{.Status}}"'

vm-logs-dagster:
	@if [ -z "$(VM_SSH)" ]; then \
	    echo "ERROR: VM_SSH must be set in $(ENV_FILE)."; \
	    exit 1; \
	fi
	ssh $(VM_SSH) 'docker logs --tail 100 -f dagster-webserver'
