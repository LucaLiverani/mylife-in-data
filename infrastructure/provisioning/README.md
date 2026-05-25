# Provisioning

First-time setup + tunnel config for the Netcup VM.

## Files

- **`bootstrap.sh`** — Idempotent root-run script for a fresh box: creates `admin` user, installs Docker, configures UFW + fail2ban + unattended-upgrades, sets hostname + timezone, generates a GitHub deploy key. Does **not** touch `sshd_config` (you harden manually after verifying key login).
- **`setup-r2.sh`** — Provisions a Cloudflare R2 bucket and writes the four `R2_*` credentials into `infrastructure/.env`.
- **`cloudflared-config.example.yml`** — Template for `~/.cloudflared/config.yml` on the VM. Maps subdomains → local service ports.
- **`.env.example`** — Deploy-time variables (VM IP, domain, tunnel UUID). Copy to `.env`, fill in, then `source .env` in any session where you run the commands below.

## Variables — set once, persist across sessions

```bash
cp infrastructure/provisioning/.env.example infrastructure/provisioning/.env
# edit infrastructure/provisioning/.env with your values
chmod 600 infrastructure/provisioning/.env
source infrastructure/provisioning/.env
```

Every command in this README uses those exports (`$VM_IP`, `$VM_USER`, `$LOCAL_KEY`, `$GH_REPO`, `$DOMAIN`, `$TUNNEL_ID`). Re-source the file in each new terminal.

## 1. Bootstrap the VM (run once)

From your laptop:

```bash
# Push your local SSH key to root on the VM
ssh-copy-id -i "${LOCAL_KEY}.pub" root@$VM_IP

# Upload and run the bootstrap script
scp infrastructure/provisioning/bootstrap.sh root@$VM_IP:/tmp/
ssh root@$VM_IP 'bash /tmp/bootstrap.sh'
```

The script prints a GitHub deploy key + next-steps checklist at the end. Save the deploy key — you'll paste it into GitHub in step 3.

## 2. Verify key login + harden SSH

```bash
# Should succeed without prompting for a password
ssh $VM_USER@$VM_IP 'whoami && docker --version'
```

If that worked, lock down SSH (bootstrap intentionally skips this):

```bash
ssh $VM_USER@$VM_IP "
  sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config &&
  sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config &&
  sudo systemctl restart ssh
"
```

## 3. Add the deploy key to GitHub

Take the public key that `bootstrap.sh` printed and add it under *Repo → Settings → Deploy keys → Add deploy key*. Title: `mylife-data`. **Leave "Allow write access" UNCHECKED** (the VM only needs to pull).

If you missed it, fetch it again:
```bash
ssh $VM_USER@$VM_IP 'cat ~/.ssh/github_mylife.pub'
```

## 4. Clone the repo + host venv + start the stack

```bash
ssh $VM_USER@$VM_IP "
  git clone $GH_REPO &&
  cd mylife-in-data/infrastructure &&
  cp .env.example .env &&
  chmod 600 .env
"

# Edit .env (interactive) — set CLICKHOUSE_PASSWORD, GRAFANA_ADMIN_PASSWORD,
# DAGSTER_POSTGRES_PASSWORD, R2 credentials. Set MYLIFE_TOKEN_WRITER=1 and
# DAGSTER_SCHEDULES_ENABLED=1 (these are the VM defaults — laptop leaves
# both as 0). Remove the DAGSTER_PORT=3030 override (only needed on dev
# machines where port 3000 is taken).
ssh -t $VM_USER@$VM_IP 'cd mylife-in-data/infrastructure && nano .env'

# Build the host venv from pyproject.toml + uv.lock. uv was installed by
# bootstrap.sh; this populates .venv/ with the project's pinned deps. Used by
# OAuth bootstraps + ad-hoc backfill scripts. Dagster has its own venv inside
# the container — they don't share.
ssh $VM_USER@$VM_IP 'cd mylife-in-data && uv sync'

# Bring everything up
ssh $VM_USER@$VM_IP 'cd mylife-in-data/infrastructure && ./start-all.sh'
```

Verify:
```bash
ssh $VM_USER@$VM_IP 'docker ps'
```

## 5. Cloudflare Tunnel

Install + connect on the VM:

```bash
ssh $VM_USER@$VM_IP "
  curl -L --output /tmp/cloudflared.deb \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb &&
  sudo dpkg -i /tmp/cloudflared.deb
"
```

Copy your existing tunnel credentials from your laptop (or create a fresh tunnel with `cloudflared tunnel login && cloudflared tunnel create mylife-data` first):

```bash
ssh $VM_USER@$VM_IP 'mkdir -p ~/.cloudflared'
scp ~/.cloudflared/$TUNNEL_ID.json $VM_USER@$VM_IP:~/.cloudflared/
scp infrastructure/provisioning/cloudflared-config.example.yml \
    $VM_USER@$VM_IP:~/.cloudflared/config.yml
```

Edit the config to fill in `$TUNNEL_ID` / `$DOMAIN`:
```bash
ssh -t $VM_USER@$VM_IP "
  sed -i \"s/<TUNNEL_ID>/$TUNNEL_ID/g; s/<YOUR_DOMAIN>/$DOMAIN/g\" ~/.cloudflared/config.yml &&
  nano ~/.cloudflared/config.yml
"
```

Route DNS for each hostname you exposed, then install as a service:

```bash
ssh $VM_USER@$VM_IP "
  for h in clickhouse dagster grafana redpanda; do
    cloudflared tunnel route dns $TUNNEL_ID \$h.$DOMAIN
  done &&
  sudo cloudflared service install &&
  sudo systemctl enable --now cloudflared
"
```

## What's still manual

- Running `.venv/bin/python ingestion/spotify/authenticate_local.py` once on the VM (and once on the laptop) to mint per-host Spotify OAuth caches. Spotify issues independent refresh tokens per OAuth grant, so each environment keeps its own `tokens/.spotify_cache` — do NOT share via SCP (the running producer container rewrites it on every 401, so copying mid-flight corrupts the cache).
- Putting Cloudflare Access in front of admin UIs (`dagster`, `grafana`, `redpanda`) with an email policy; `clickhouse.<DOMAIN>` gets a Service Token policy so the dashboard Pages Functions can authenticate.
- Setting up `clickhouse-backup` → R2 (separate follow-up).
