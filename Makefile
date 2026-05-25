# Convenience targets for the laptop ↔ VM workflow.
# See OPERATIONS.md "Daily dev cycle" for the full picture.

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

.PHONY: help deploy-vm pull-tokens vm-status vm-logs-dagster

help:
	@echo "mylife-in-data — workflow targets"
	@echo
	@echo "  make deploy-vm       Push dev branch + run infrastructure/deploy.sh on the VM."
	@echo "  make pull-tokens     Copy Google OAuth tokens from VM → laptop ClickHouse."
	@echo "  make vm-status       Show docker ps on the VM."
	@echo "  make vm-logs-dagster Tail dagster-webserver logs on the VM."
	@echo
	@echo "VM endpoint comes from $(ENV_FILE) (VM_SSH = ssh alias or user@host,"
	@echo "VM_REPO_PATH = path on VM). Override on the CLI: make deploy-vm VM_SSH=other"

deploy-vm:
	@if [ -z "$(VM_SSH)" ]; then \
	    echo "ERROR: VM_SSH must be set in $(ENV_FILE) (ssh alias like 'perry' or 'user@host')."; \
	    exit 1; \
	fi
	@echo "→ Pushing dev branch to GitHub..."
	git push origin dev
	@echo "→ Triggering deploy on $(VM_SSH):$(VM_REPO_PATH)..."
	ssh $(VM_SSH) 'cd $(VM_REPO_PATH) && ./infrastructure/deploy.sh'

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
