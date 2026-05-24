#!/usr/bin/env bash
# install-cloudflared.sh — VM-side installer for the Cloudflare Tunnel daemon.
#
# Runs ON the VM (Debian/Ubuntu, any arch dpkg supports). Expects:
#   - ~/.cloudflared/config.yml         (ingress rules — scp'd from laptop)
#   - ~/.cloudflared/<TUNNEL_ID>.json   (tunnel credentials — scp'd from laptop)
#
# Idempotent: safe to re-run after upgrades or config changes.
#
# Usage (from your laptop):
#   ssh -t $VM_USER@$VM_IP 'bash /path/to/install-cloudflared.sh'
#
# DEPLOYMENT_PLAN.md → Phase 3.2

set -euo pipefail

ME=$(whoami)
HOMEDIR="$HOME"
USER_CF="$HOMEDIR/.cloudflared"
SYS_CF="/etc/cloudflared"

if [ ! -f "$USER_CF/config.yml" ]; then
  echo "ERROR: $USER_CF/config.yml missing — scp it from your laptop first." >&2
  exit 1
fi
CRED_FILE=$(find "$USER_CF" -maxdepth 1 -name '*.json' -print -quit)
if [ -z "$CRED_FILE" ]; then
  echo "ERROR: no <UUID>.json credentials file in $USER_CF — scp it first." >&2
  exit 1
fi
echo "==> running as: $ME  home: $HOMEDIR"
echo "==> using config:   $USER_CF/config.yml"
echo "==> using creds:    $CRED_FILE"

# ── 1. Install / upgrade the cloudflared deb ──────────────────────────────
ARCH=$(dpkg --print-architecture)
echo "==> dpkg arch: $ARCH"
DEB_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}.deb"

echo "==> downloading $DEB_URL"
curl -fsSL --output /tmp/cloudflared.deb "$DEB_URL"

echo "==> installing cloudflared (sudo required)"
sudo dpkg -i /tmp/cloudflared.deb
cloudflared --version

# ── 2. Promote config + creds into /etc/cloudflared/ ──────────────────────
#    The systemd unit installed below runs as a system user that cannot
#    read $HOME/.cloudflared/, so we copy into /etc/ and rewrite the
#    credentials-file path inside the config.
echo "==> promoting config + creds to $SYS_CF/"
sudo mkdir -p "$SYS_CF"
sudo cp "$USER_CF/config.yml" "$SYS_CF/config.yml"
sudo cp "$CRED_FILE" "$SYS_CF/"
sudo sed -i "s|$USER_CF/|$SYS_CF/|g" "$SYS_CF/config.yml"
sudo chmod 600 "$SYS_CF"/*.json
sudo chmod 644 "$SYS_CF/config.yml"

# ── 3. Install + enable the systemd service ───────────────────────────────
# `service install` is idempotent; if a unit already exists it no-ops with
# a non-zero exit, which we tolerate.
echo "==> installing systemd service"
sudo cloudflared service install || true
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared
sudo systemctl restart cloudflared    # pick up any config changes

# ── 4. Show status so the operator can confirm health ─────────────────────
echo
echo "==> systemctl status:"
sudo systemctl status cloudflared --no-pager 2>&1 | head -15 || true
echo
echo "==> last 15 journal lines:"
sudo journalctl -u cloudflared --no-pager -n 15 || true
echo
echo "==> done."
