# Server Setup Guide

A simple guide for provisioning a fresh Debian server with a non-root admin user, SSH-key-only access, and a convenient client-side shortcut.

Tested on Debian 13 (trixie), ARM64. Should work on any modern Debian/Ubuntu.

> **Before running any command below**, set the server IP in your shell:
> ```bash
> export IP=YOUR.SERVER.IP.HERE
> ```
> This keeps the IP out of this document. Set it once per terminal session.

---

## What You'll End Up With

- A non-root admin user (this guide uses `perry` — substitute your own name)
- Root SSH login restricted to keys only
- All password-based SSH login disabled
- A `ssh perry` shortcut on your laptop

---

## Prerequisites

- A fresh Debian/Ubuntu server with:
  - A public IP
  - A root password (usually provided by the hosting provider)
  - SSH host key fingerprints (provided by the hosting provider — needed to verify identity on first connect)
- A laptop/desktop you can SSH from

---

## Step 1 — Generate an SSH Key on Your Laptop

Skip this if you already have `~/.ssh/id_ed25519`.

```bash
ssh-keygen -t ed25519 -C "describe-this-device"
```

Press Enter through the prompts. A passphrase is recommended.

This creates:
- `~/.ssh/id_ed25519` — **private key, never share, never commit**
- `~/.ssh/id_ed25519.pub` — public key, safe to share

---

## Step 2 — First Login as Root

```bash
ssh root@$IP
```

SSH will show the server's fingerprint:

```
ED25519 key fingerprint is SHA256:xxxx...
Are you sure you want to continue connecting (yes/no)?
```

**Verify it matches one of the fingerprints provided by your host** before typing `yes`. If it doesn't match, stop — something is wrong.

Then enter the root password from your hosting provider.

---

## Step 3 — Change the Root Password

Since the original password traveled by email/web, rotate it immediately:

```bash
passwd
```

---

## Step 4 — Update the System

```bash
apt update && apt full-upgrade -y
```

---

## Step 5 — Create a Non-Root Admin User

Replace `perry` with whatever name you want for your admin user. The rest of this guide assumes `perry` — adjust accordingly.

```bash
adduser perry
usermod -aG sudo perry
```

`adduser` will prompt for a password and some optional info. The optional fields can be left blank with Enter.

---

## Step 6 — Install Your SSH Key for the New User

On your **laptop**, print your public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the entire line (starts with `ssh-ed25519 AAAA...`).

Back on the **server** (as root), install it for the new user:

```bash
mkdir -p /home/perry/.ssh
echo 'PASTE_YOUR_PUBLIC_KEY_HERE' > /home/perry/.ssh/authorized_keys
chown -R perry:perry /home/perry/.ssh
chmod 700 /home/perry/.ssh
chmod 600 /home/perry/.ssh/authorized_keys
```

---

## Step 7 — Test Key Login Before Locking Down

**This step is critical.** If you disable password auth before key auth works, you'll be locked out and will need your provider's rescue console to recover.

On your **laptop**, in a new terminal (leave the root session open):

```bash
ssh perry@$IP
```

Must log in **without prompting for a password**. If it asks for a password or fails, stop and debug before continuing.

---

## Step 8 — Harden SSH

Back in the root session on the server:

```bash
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
# Debian 13 may have these split into /etc/ssh/sshd_config.d/ — clean those too:
grep -rl "PasswordAuthentication" /etc/ssh/sshd_config.d/ 2>/dev/null | xargs -r sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/'
systemctl restart ssh
```

Verify the result:

```bash
grep -E "^(PermitRootLogin|PasswordAuthentication)" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null
```

You should see `PermitRootLogin prohibit-password` and `PasswordAuthentication no`.

---

## Step 9 — Verify the Hardening from the Laptop

```bash
# Should still work (key login):
ssh perry@$IP

# Should be rejected with "Permission denied (publickey)":
ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no perry@$IP
```

If both behave as expected, hardening is complete. You can now close the root session.

---

## Step 10 — Add a Shortcut on Your Laptop

Edit `~/.ssh/config` and add (replace `YOUR.SERVER.IP.HERE` with the real IP — SSH config files don't expand `$IP`):

```
Host perry
    HostName YOUR.SERVER.IP.HERE
    User perry
    IdentityFile ~/.ssh/id_ed25519
```

Then:

```bash
chmod 600 ~/.ssh/config
ssh perry
```

From now on, `ssh perry` is enough.

---

## Step 11 — Optional: Day-One Hardening

On the server, as `perry`:

```bash
# Firewall — only SSH open, deny everything else by default
sudo apt install ufw -y
sudo ufw allow 22/tcp
sudo ufw --force enable

# Automatic security updates
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades

# Brute-force throttling (mostly belt + suspenders once password auth is off)
sudo apt install fail2ban -y
sudo systemctl enable --now fail2ban
```

---

## Adding Access from Another Device

Repeat these steps for any new laptop/desktop/phone:

### 1. Generate a key on the new device

```bash
ssh-keygen -t ed25519 -C "describe-this-device"
```

### 2. Print the new public key

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the entire line.

### 3. Append it on the server

From an **already-trusted device**:

```bash
ssh perry
echo 'PASTE_THE_NEW_PUBLIC_KEY_HERE' >> ~/.ssh/authorized_keys
```

### 4. Test from the new device

```bash
export IP=YOUR.SERVER.IP.HERE
ssh perry@$IP
```

### 5. (Optional) Add the shortcut on the new device

Same `~/.ssh/config` block as Step 10.

---

## Removing Access from a Device

If a device is lost, stolen, or just retired:

1. SSH into the server from any trusted device
2. Open the authorized keys file: `nano ~/.ssh/authorized_keys`
3. Delete the line for that device (the comment at the end of each line — set via `-C` in `ssh-keygen` — tells you which device it is)
4. Save (`Ctrl+O`, Enter, `Ctrl+X`)

---

## Useful Commands

| Task | Command |
|---|---|
| Connect to server | `ssh perry` |
| Copy file to server | `scp file.txt perry:~/` |
| Copy file from server | `scp perry:~/file.txt .` |
| Sync a folder to server | `rsync -avz ./folder/ perry:~/folder/` |
| Check who's logged in | `who` (on the server) |
| List authorized keys | `cat ~/.ssh/authorized_keys` (on the server) |
| Update the server | `sudo apt update && sudo apt full-upgrade -y` |
| Leave the SSH session | `exit` or `Ctrl+D` |
| Force-close a frozen SSH session | `Enter`, then `~`, then `.` |

---

## Persisting `$IP` (Optional)

If you'd rather not retype `export IP=...` every session, add it to your shell rc file:

```bash
echo 'export IP=YOUR.SERVER.IP.HERE' >> ~/.bashrc   # or ~/.zshrc
source ~/.bashrc
```

Note: anyone with read access to your home directory can see it there. For sensitive values, prefer a `.env` file that's `chmod 600` and sourced only when needed. **Do not** commit the rc file or `.env` to the repo with the real IP inside.
