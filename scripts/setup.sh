#!/usr/bin/env bash
# setup.sh — One-time VPS setup for Clawbot
# Run as a non-root user with sudo access.
# This script: installs Docker, creates the deploy user, sets up the project, and configures cron.

set -euo pipefail

PROJECT_DIR="/opt/clawbot"
DEPLOY_USER="clawbot"
CRON_BACKUP="0 2 * * * ${PROJECT_DIR}/scripts/backup_db.sh >> /var/log/clawbot-backup.log 2>&1"

echo "═══════════════════════════════════════════════"
echo "  Clawbot VPS Setup"
echo "═══════════════════════════════════════════════"

# ─── 1. System packages ───────────────────────────────────────────────────────
echo "→ Updating system packages..."
sudo apt-get update -q
sudo apt-get install -y -q curl git jq ufw

# ─── 2. Docker ────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "→ Installing Docker..."
  curl -fsSL https://get.docker.com | sudo sh
  sudo systemctl enable docker
  sudo systemctl start docker
else
  echo "→ Docker already installed: $(docker --version)"
fi

# ─── 3. Deploy user ───────────────────────────────────────────────────────────
if ! id "${DEPLOY_USER}" &>/dev/null; then
  echo "→ Creating deploy user: ${DEPLOY_USER}"
  sudo useradd -m -s /bin/bash "${DEPLOY_USER}"
  sudo usermod -aG docker "${DEPLOY_USER}"
else
  echo "→ Deploy user already exists: ${DEPLOY_USER}"
fi

# ─── 4. Project directory ─────────────────────────────────────────────────────
echo "→ Creating project directory: ${PROJECT_DIR}"
sudo mkdir -p "${PROJECT_DIR}"
sudo mkdir -p "${PROJECT_DIR}/backups"
sudo chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${PROJECT_DIR}"

# ─── 5. Copy project files ────────────────────────────────────────────────────
echo "→ Copying project files..."
# Assumes you're running this from inside the clawbot/ directory
sudo cp -r . "${PROJECT_DIR}/"
sudo chown -R "${DEPLOY_USER}:${DEPLOY_USER}" "${PROJECT_DIR}"
sudo chmod +x "${PROJECT_DIR}/scripts/"*.sh

# ─── 6. .env setup ───────────────────────────────────────────────────────────
if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
  echo "→ Creating .env from .env.example..."
  sudo cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
  sudo chown "${DEPLOY_USER}:${DEPLOY_USER}" "${PROJECT_DIR}/.env"
  sudo chmod 600 "${PROJECT_DIR}/.env"
  echo ""
  echo "  ⚠️  IMPORTANT: Edit ${PROJECT_DIR}/.env before starting services"
  echo "  Fill in: AZURE_API_KEY, AZURE_API_BASE, POSTGRES_PASSWORD, REDIS_PASSWORD,"
  echo "           LITELLM_MASTER_KEY, SECRET_KEY, N8N_ENCRYPTION_KEY, GRAFANA_PASSWORD"
  echo ""
else
  echo "→ .env already exists, skipping."
fi

# ─── 7. Firewall ─────────────────────────────────────────────────────────────
echo "→ Configuring firewall (UFW)..."
sudo ufw allow 22/tcp comment "SSH"
sudo ufw allow 80/tcp comment "HTTP"
sudo ufw allow 443/tcp comment "HTTPS"
sudo ufw --force enable
echo "→ UFW status:"
sudo ufw status

# ─── 8. Backup cron ───────────────────────────────────────────────────────────
echo "→ Setting up nightly backup cron..."
(sudo crontab -u "${DEPLOY_USER}" -l 2>/dev/null | grep -v "backup_db.sh"; echo "${CRON_BACKUP}") \
  | sudo crontab -u "${DEPLOY_USER}" -

# ─── 9. Log file ──────────────────────────────────────────────────────────────
sudo touch /var/log/clawbot-backup.log
sudo chown "${DEPLOY_USER}:${DEPLOY_USER}" /var/log/clawbot-backup.log

echo ""
echo "═══════════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Edit ${PROJECT_DIR}/.env with your credentials"
echo "  2. Update caddy/Caddyfile with your domain (aliviostudio.com)"
echo "  3. Point DNS A records for api., grafana., n8n., hooks. to this VPS IP"
echo "  4. Run: cd ${PROJECT_DIR} && sudo -u ${DEPLOY_USER} docker compose up -d"
echo "  5. Check logs: docker compose logs -f control-api"
echo "  6. Test: curl https://api.aliviostudio.com/health"
echo "═══════════════════════════════════════════════"
