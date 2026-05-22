#!/usr/bin/env bash
# bootstrap.sh — Idempotent first-time setup for a fresh Netcup ARM VPS.
#
# Run AS ROOT on a fresh box. Safe to re-run.
#
# Usage from your local machine:
#   ssh-copy-id -i ~/.ssh/id_ed25519_personal.pub root@<VM_IP>
#   scp infrastructure/provisioning/bootstrap.sh root@<VM_IP>:/tmp/
#   ssh root@<VM_IP> 'bash /tmp/bootstrap.sh'
#
# What it does:
#   1. Sets hostname + timezone
#   2. Creates a non-root sudoer + docker user (`admin` by default)
#   3. Copies root's authorized_keys to the new user
#   4. Installs Docker + Compose plugin (official convenience script)
#   5. Configures UFW: deny inbound, allow 22 only
#   6. Installs fail2ban (SSH bruteforce protection)
#   7. Enables unattended-upgrades (security patches)
#   8. Generates a GitHub deploy key for the data platform repo + an SSH config
#      entry so `git clone git@github.com:...` resolves to it
#   9. Prints the deploy key + next-step instructions
#
# What it does NOT do:
#   - It does NOT touch /etc/ssh/sshd_config. Password auth and root login stay
#     as-is. Harden manually after verifying key login works (see README).

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Configuration (override via env vars on invocation if needed)
# ─────────────────────────────────────────────────────────────────────────────
USERNAME="${USERNAME:-admin}"
TIMEZONE="${TIMEZONE:-Europe/Zurich}"
HOSTNAME_NEW="${HOSTNAME_NEW:-mylife-data}"
GH_DEPLOY_KEY_NAME="github_mylife"
GH_REPO_HOST="github.com"

# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight
# ─────────────────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  echo "ERROR: must be run as root." >&2
  exit 1
fi

# Need at least one path of key-based access. After SSH hardening per
# infrastructure/server/README.md root usually has no authorized_keys; in that
# case the target user must already exist with their own key installed.
USER_HOME_PRECHECK="/home/${USERNAME:-admin}"
if [[ ! -s /root/.ssh/authorized_keys ]] && [[ ! -s "$USER_HOME_PRECHECK/.ssh/authorized_keys" ]]; then
  echo "ERROR: no SSH key found in /root/.ssh/authorized_keys or $USER_HOME_PRECHECK/.ssh/authorized_keys." >&2
  echo "       Either ssh-copy-id root first, or follow infrastructure/server/README.md to" >&2
  echo "       create the target user with key access before running this script." >&2
  exit 1
fi

echo "▶ bootstrap.sh starting on $(hostname) at $(date -Is)"
echo "  username=$USERNAME  hostname=$HOSTNAME_NEW  timezone=$TIMEZONE"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 1. Hostname + timezone
# ─────────────────────────────────────────────────────────────────────────────
echo "▶ Setting hostname → $HOSTNAME_NEW"
hostnamectl set-hostname "$HOSTNAME_NEW"
# Make sure /etc/hosts has the new hostname so sudo doesn't whine
if ! grep -q "$HOSTNAME_NEW" /etc/hosts; then
  echo "127.0.1.1   $HOSTNAME_NEW" >> /etc/hosts
fi

echo "▶ Setting timezone → $TIMEZONE"
timedatectl set-timezone "$TIMEZONE"

# ─────────────────────────────────────────────────────────────────────────────
# 2. System update + base packages
# ─────────────────────────────────────────────────────────────────────────────
echo "▶ apt update + upgrade"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq

echo "▶ Installing base packages"
apt-get install -y -qq \
  ca-certificates curl gnupg lsb-release \
  git jq unzip wget \
  ufw fail2ban unattended-upgrades \
  htop ncdu vim tmux

# ─────────────────────────────────────────────────────────────────────────────
# 3. Non-root user with sudo + (eventually) docker group membership
# ─────────────────────────────────────────────────────────────────────────────
if id -u "$USERNAME" >/dev/null 2>&1; then
  echo "▶ User $USERNAME already exists — skipping creation"
else
  echo "▶ Creating user $USERNAME"
  adduser --disabled-password --gecos "" "$USERNAME"
  usermod -aG sudo "$USERNAME"
  # Passwordless sudo (no password set; SSH key is the only auth)
  echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-"$USERNAME"
  chmod 0440 /etc/sudoers.d/90-"$USERNAME"
fi

# If the target user has no key yet, seed it from root's authorized_keys.
# Idempotent: if the user already has their own keys (SSH-hardened workflow),
# leave them alone.
USER_HOME="/home/$USERNAME"
mkdir -p "$USER_HOME/.ssh"
if [[ ! -s "$USER_HOME/.ssh/authorized_keys" ]] && [[ -s /root/.ssh/authorized_keys ]]; then
  cp /root/.ssh/authorized_keys "$USER_HOME/.ssh/authorized_keys"
  echo "  ✓ SSH keys seeded from root → $USER_HOME/.ssh/authorized_keys"
else
  echo "  ✓ $USERNAME already has SSH keys — leaving as-is"
fi
chown -R "$USERNAME:$USERNAME" "$USER_HOME/.ssh"
chmod 700 "$USER_HOME/.ssh"
chmod 600 "$USER_HOME/.ssh/authorized_keys"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Docker + Compose plugin
# ─────────────────────────────────────────────────────────────────────────────
if command -v docker >/dev/null 2>&1; then
  echo "▶ Docker already installed ($(docker --version)) — skipping"
else
  echo "▶ Installing Docker (official convenience script)"
  curl -fsSL https://get.docker.com | sh
fi

# Make sure admin is in the docker group
usermod -aG docker "$USERNAME"

systemctl enable --now docker
echo "  ✓ Docker enabled and running"

# ─────────────────────────────────────────────────────────────────────────────
# 5. Firewall (UFW)
# ─────────────────────────────────────────────────────────────────────────────
echo "▶ Configuring UFW (deny inbound, allow 22 only)"
ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'ssh'
ufw --force enable
echo "  ✓ UFW active. Cloudflare Tunnel makes outbound connections — no other ports needed."

# ─────────────────────────────────────────────────────────────────────────────
# 6. fail2ban (default jails include sshd)
# ─────────────────────────────────────────────────────────────────────────────
echo "▶ Enabling fail2ban"
systemctl enable --now fail2ban
echo "  ✓ fail2ban running"

# ─────────────────────────────────────────────────────────────────────────────
# 7. unattended-upgrades (auto-install security patches)
# ─────────────────────────────────────────────────────────────────────────────
echo "▶ Enabling unattended-upgrades for security patches"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
systemctl enable --now unattended-upgrades
echo "  ✓ unattended-upgrades enabled"

# ─────────────────────────────────────────────────────────────────────────────
# 8. GitHub deploy key (per-machine, read-only intent)
# ─────────────────────────────────────────────────────────────────────────────
KEY_PATH="$USER_HOME/.ssh/$GH_DEPLOY_KEY_NAME"
if [[ -f "$KEY_PATH" ]]; then
  echo "▶ GitHub deploy key already exists at $KEY_PATH — skipping generation"
else
  echo "▶ Generating GitHub deploy key → $KEY_PATH"
  sudo -u "$USERNAME" ssh-keygen -t ed25519 -N "" \
    -f "$KEY_PATH" \
    -C "$USERNAME@$HOSTNAME_NEW deploy-key"
fi

# SSH config so github.com uses the deploy key
SSH_CONFIG="$USER_HOME/.ssh/config"
if ! grep -q "Host $GH_REPO_HOST" "$SSH_CONFIG" 2>/dev/null; then
  echo "▶ Adding SSH config entry for $GH_REPO_HOST"
  cat >> "$SSH_CONFIG" <<EOF

Host $GH_REPO_HOST
  HostName $GH_REPO_HOST
  User git
  IdentityFile $KEY_PATH
  IdentitiesOnly yes
EOF
  chown "$USERNAME:$USERNAME" "$SSH_CONFIG"
  chmod 600 "$SSH_CONFIG"
fi

# Pre-add github.com to known_hosts so `git clone` doesn't prompt
KNOWN_HOSTS="$USER_HOME/.ssh/known_hosts"
if ! grep -q "$GH_REPO_HOST" "$KNOWN_HOSTS" 2>/dev/null; then
  ssh-keyscan -H "$GH_REPO_HOST" >> "$KNOWN_HOSTS" 2>/dev/null
  chown "$USERNAME:$USERNAME" "$KNOWN_HOSTS"
  chmod 600 "$KNOWN_HOSTS"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Done — print next steps
# ─────────────────────────────────────────────────────────────────────────────
DEPLOY_PUBKEY=$(cat "$KEY_PATH.pub")

cat <<EOF

═══════════════════════════════════════════════════════════════════════════════
 ✓ bootstrap.sh complete
═══════════════════════════════════════════════════════════════════════════════

  User:       $USERNAME   (sudo + docker, no password set)
  Hostname:   $HOSTNAME_NEW
  Timezone:   $TIMEZONE
  Docker:     $(docker --version)
  Firewall:   UFW active — only 22/tcp open
  fail2ban:   active
  Updates:    unattended-upgrades enabled

───────────────────────────────────────────────────────────────────────────────
 NEXT STEPS (in this order)
───────────────────────────────────────────────────────────────────────────────

 1. From your laptop, verify key login works as the new user:

      ssh $USERNAME@<VM_IP>

    If it works, you're safe to harden SSH manually:

      sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
      sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
      sudo systemctl restart ssh

 2. Add this DEPLOY KEY to GitHub:
       Repo → Settings → Deploy keys → Add deploy key
       Title:           $HOSTNAME_NEW
       Allow write:     leave UNCHECKED
       Key (paste it):

$DEPLOY_PUBKEY

 3. Clone the repo as $USERNAME:

      ssh $USERNAME@<VM_IP>
      git clone git@github.com:<you>/mylife-in-data.git
      cd mylife-in-data
      cp .env.example .env
      \$EDITOR .env       # fill in credentials

 4. Bring the stack up:

      cd infrastructure
      ./start-all.sh

 5. Install cloudflared and wire up the tunnel
    (see infrastructure/provisioning/cloudflared-config.example.yml)

═══════════════════════════════════════════════════════════════════════════════
EOF
