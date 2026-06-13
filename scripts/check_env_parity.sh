#!/usr/bin/env bash
# check_env_parity.sh — Keep the laptop and VM infrastructure/.env in sync.
#
# The platform runs in two places (laptop = dev, VM = prod) off ONE .env layout.
# Every shared secret/credential (Spotify, R2, Google, LLM, webhook tokens,
# ClickHouse/Grafana/Umami passwords, …) MUST hold the same value in both files,
# so a value set on one side (e.g. ALERT_WEBHOOK_URL/TOKEN, which only ever got
# filled in on the VM) is never silently absent on the other.
#
# A small set of keys is INTENTIONALLY per-environment and is excluded from the
# parity check (see EXCLUDE_KEYS below): the documented laptop↔VM split flags
# (PLATFORM_ENV, ALERTING_ENABLED, MYLIFE_TOKEN_WRITER, DAGSTER_SCHEDULES_ENABLED)
# plus deploy-target / per-instance keys (VM_SSH, VM_REPO_PATH,
# CLICKHOUSE_DBT_DEV_PASSWORD). Forcing those identical would, e.g., make the
# laptop a second OAuth-token writer — see .env.example and CLAUDE.md.
#
# The VM is the source of truth: --fix pulls VM values into the LOCAL file only.
# This script is READ-ONLY on the VM (it never writes there) and NEVER prints a
# secret value — drift is reported by key name + status only.
#
# Reads:
#   infrastructure/.env  — local file, and VM_SSH / VM_REPO_PATH to reach the VM
#   <VM>:<repo>/infrastructure/.env  — fetched over SSH into a chmod-600 tempfile
#
# Usage:
#   ./scripts/check_env_parity.sh          # report drift, exit 1 if any (CI-style)
#   ./scripts/check_env_parity.sh --fix    # pull VM values into the local .env
#
# Requires: ssh access to the VM (key in ~/.ssh; alias/host in VM_SSH).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_ENV="$REPO_ROOT/infrastructure/.env"

FIX=0
case "${1:-}" in
    --fix) FIX=1 ;;
    -h|--help)
        sed -n '2,33p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
        exit 0 ;;
    "") ;;
    *) echo "ERROR: unknown argument '$1' (use --fix or --help)." >&2; exit 2 ;;
esac

# Keys that are SUPPOSED to differ between laptop and VM — never compared,
# never synced. Keep this list in step with .env.example's split-flag section.
EXCLUDE_KEYS=" PLATFORM_ENV ALERTING_ENABLED MYLIFE_TOKEN_WRITER DAGSTER_SCHEDULES_ENABLED VM_SSH VM_REPO_PATH CLICKHOUSE_DBT_DEV_PASSWORD "

MISSING='__ENV_PARITY_KEY_ABSENT__'   # sentinel: key absent (vs. present-but-empty "")

if [ ! -f "$LOCAL_ENV" ]; then
    echo "ERROR: $LOCAL_ENV not found." >&2
    exit 1
fi

VM_SSH="$(grep -E '^VM_SSH='       "$LOCAL_ENV" | head -n1 | cut -d= -f2- || true)"
VM_REPO_PATH="$(grep -E '^VM_REPO_PATH=' "$LOCAL_ENV" | head -n1 | cut -d= -f2- || true)"
VM_REPO_PATH="${VM_REPO_PATH:-~/mylife-in-data}"
if [ -z "$VM_SSH" ]; then
    echo "ERROR: VM_SSH not set in $LOCAL_ENV (ssh alias like 'perry' or 'user@host')." >&2
    exit 1
fi

# Fetch the VM .env into a private tempfile; always clean it up.
VM_ENV="$(mktemp)"
chmod 600 "$VM_ENV"
trap 'rm -f "$VM_ENV"' EXIT

echo "→ Fetching infrastructure/.env from $VM_SSH ..."
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$VM_SSH" \
        "cat $VM_REPO_PATH/infrastructure/.env" > "$VM_ENV"; then
    echo "ERROR: could not read the VM .env over SSH (VM_SSH=$VM_SSH)." >&2
    exit 1
fi

# Last assignment wins (dotenv semantics); sentinel if the key is absent.
get_val() { # <file> <key>
    local line
    line="$(grep -E "^$2=" "$1" | tail -n1 || true)"
    if [ -z "$line" ]; then printf '%s' "$MISSING"; return; fi
    printf '%s' "${line#*=}"
}

# Union of declared keys across both files, minus the excluded set.
ALL_KEYS="$( { grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' "$LOCAL_ENV" || true; \
               grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' "$VM_ENV"    || true; } \
             | cut -d= -f1 | sort -u )"

declare -A SYNC=()        # key -> VM value to write into local (VM→local drift)
ERRORS=()                 # human-readable lines (NO values) for fixable drift
WARNS=()                  # local-only values the VM lacks (informational)

while IFS= read -r key; do
    [ -n "$key" ] || continue
    [[ "$EXCLUDE_KEYS" == *" $key "* ]] && continue

    lv="$(get_val "$LOCAL_ENV" "$key")"
    vv="$(get_val "$VM_ENV" "$key")"

    [ "$lv" = "$vv" ] && continue   # identical (incl. both empty) → in sync

    local_has=0; [ "$lv" != "$MISSING" ] && [ -n "$lv" ] && local_has=1
    vm_has=0;    [ "$vv" != "$MISSING" ] && [ -n "$vv" ] && vm_has=1

    if [ "$vm_has" = 1 ]; then
        # VM has a real value; local is empty/absent/different → sync VM→local.
        if [ "$lv" = "$MISSING" ]; then reason="absent in local"
        elif [ -z "$lv" ];        then reason="empty in local"
        else                            reason="differs from VM"; fi
        ERRORS+=("$key — $reason")
        SYNC["$key"]="$vv"
    elif [ "$local_has" = 1 ]; then
        # Local has a value the VM lacks. Not auto-synced (script never writes
        # the VM); surfaced for a human to reconcile.
        if [ "$vv" = "$MISSING" ]; then reason="not present on VM"
        else                            reason="empty on VM"; fi
        WARNS+=("$key — $reason")
    fi
done <<< "$ALL_KEYS"

echo
if [ "${#ERRORS[@]}" -eq 0 ] && [ "${#WARNS[@]}" -eq 0 ]; then
    echo "✓ Shared secrets/config are in sync (excluded per-env keys:${EXCLUDE_KEYS})."
    exit 0
fi

if [ "${#ERRORS[@]}" -gt 0 ]; then
    echo "Local out of sync with VM (VM is source of truth):"
    for e in "${ERRORS[@]}"; do echo "  ✗ $e"; done
fi
if [ "${#WARNS[@]}" -gt 0 ]; then
    echo "Present locally but not on the VM (reconcile by hand if intended):"
    for w in "${WARNS[@]}"; do echo "  ⚠ $w"; done
fi
echo

if [ "${#ERRORS[@]}" -eq 0 ]; then
    # Only local-only warnings remain — nothing this script fixes; not a failure.
    exit 0
fi

if [ "$FIX" -eq 0 ]; then
    echo "Run with --fix to pull the VM values into $LOCAL_ENV."
    exit 1
fi

# --fix: rewrite the local .env, replacing each drifting key's line in place
# (preserving comments/order) and appending any keys absent from the local file.
echo "→ Applying ${#SYNC[@]} value(s) from the VM into $LOCAL_ENV ..."
TMP="$(mktemp)"; chmod 600 "$TMP"
declare -A WRITTEN=()
while IFS= read -r line || [ -n "$line" ]; do
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)= ]]; then
        k="${BASH_REMATCH[1]}"
        if [ -n "${SYNC[$k]+x}" ]; then
            printf '%s=%s\n' "$k" "${SYNC[$k]}" >> "$TMP"
            WRITTEN["$k"]=1
            continue
        fi
    fi
    printf '%s\n' "$line" >> "$TMP"
done < "$LOCAL_ENV"

appended=0
for k in "${!SYNC[@]}"; do
    if [ -z "${WRITTEN[$k]+x}" ]; then
        if [ "$appended" -eq 0 ]; then
            printf '\n# ── Synced from VM by scripts/check_env_parity.sh ──\n' >> "$TMP"
            appended=1
        fi
        printf '%s=%s\n' "$k" "${SYNC[$k]}" >> "$TMP"
    fi
done

cp "$LOCAL_ENV" "$LOCAL_ENV.bak"
mv "$TMP" "$LOCAL_ENV"
chmod 600 "$LOCAL_ENV"
echo "✓ Synced: ${!SYNC[*]}"
echo "  (previous file saved as infrastructure/.env.bak)"
