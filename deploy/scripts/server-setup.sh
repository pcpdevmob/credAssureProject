#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 VM for the hosted deployment (docs/deployment/azure.md §6).
#   sudo bash deploy/scripts/server-setup.sh
# Installs Docker Engine + Compose plugin, a firewall allowing only SSH, HTTP and HTTPS, a 4 GB swap
# file, sqlite3 (backups), automatic security updates, and the nightly case.db backup (cron).
# Safe to run twice. Changes nothing inside the repo except creating var/ with the right owner.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OWNER="${SUDO_USER:-azureuser}"

echo "== packages"
apt-get update -q
apt-get install -y -q ca-certificates curl gnupg ufw sqlite3 unattended-upgrades git

echo "== Docker (official apt repository)"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    >/etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker
usermod -aG docker "$OWNER" # takes effect at the next SSH login

echo "== firewall: 22, 80, 443 only (the Azure network security group limits SSH to your IP)"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "== swap (4 GB): headroom while the embedder and reranker load"
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >>/etc/fstab
fi

echo "== automatic security updates"
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== data folders (the gateway container runs as uid 10001)"
mkdir -p "$REPO/var/certs" "$REPO/var/backups"
chown -R 10001:10001 "$REPO/var"
chown -R "$OWNER" "$REPO/var/backups"

echo "== nightly backup of case.db at 02:15 IST (7 kept)"
cat >/etc/cron.d/credassure-backup <<CRON
CRON_TZ=Asia/Kolkata
15 2 * * * root $REPO/deploy/scripts/nightly-backup.sh >>/var/log/credassure-backup.log 2>&1
CRON
chmod 644 /etc/cron.d/credassure-backup

echo
echo "Done. Log out and back in (docker group), then continue with docs/deployment/azure.md step 7."
