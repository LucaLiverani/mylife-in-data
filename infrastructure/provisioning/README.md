# Provisioning

First-time setup + tunnel config for the Netcup VM.

## Files

- **`bootstrap.sh`** — Idempotent root-run script for a fresh box: creates `admin` user, installs Docker, configures UFW + fail2ban + unattended-upgrades, sets hostname + timezone, generates a GitHub deploy key. Does **not** touch `sshd_config` (you harden manually after verifying key login).
- **`cloudflared-config.example.yml`** — Template for `~/.cloudflared/config.yml` on the VM. Maps subdomains → local service ports.

## Variables — set once per session

Open a terminal and export these. Every command below uses them.

```bash
export VM_IP=
export VM_USER=
export LOCAL_KEY=
export GH_REPO=
export TUNNEL_ID=
export DOMAIN=
```

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

## 4. Clone the repo + start the stack

```bash
ssh $VM_USER@$VM_IP "
  git clone $GH_REPO &&
  cd mylife-in-data &&
  cp .env.example .env
"

# Edit .env (interactive)
ssh -t $VM_USER@$VM_IP 'cd mylife-in-data && nano .env'

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
  for h in ch dagster airflow grafana; do
    cloudflared tunnel route dns $TUNNEL_ID \$h.$DOMAIN
  done &&
  sudo cloudflared service install &&
  sudo systemctl enable --now cloudflared
"
```

## What's still manual

- Adding the Spotify token cache to Airflow Variables (the auth script prints what to paste; see `ingestion/spotify/README.md`).
- Putting Cloudflare Access in front of admin UIs (`airflow`, `dagster`, `grafana`) so only you can hit them.
- Setting up `clickhouse-backup` → R2 (separate follow-up).
