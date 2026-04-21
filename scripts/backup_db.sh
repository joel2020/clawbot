#!/usr/bin/env bash
# backup_db.sh — Nightly Postgres backup
# Dumps the database to /backups with a timestamp, keeps last 14 days.
# Add to crontab: 0 2 * * * /opt/clawbot/scripts/backup_db.sh >> /var/log/clawbot-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="/opt/clawbot/backups"
CONTAINER="postgres"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/clawbot_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=14

# Load env from .env file (adjust path if needed)
ENV_FILE="/opt/clawbot/.env"
if [[ -f "$ENV_FILE" ]]; then
  export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

echo "[$(date -Iseconds)] Starting backup → ${BACKUP_FILE}"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Dump and compress
docker exec "${CONTAINER}" pg_dump \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --no-password \
  | gzip > "${BACKUP_FILE}"

echo "[$(date -Iseconds)] Backup complete: $(du -sh "${BACKUP_FILE}" | cut -f1)"

# Remove backups older than RETENTION_DAYS
find "${BACKUP_DIR}" -name "clawbot_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
echo "[$(date -Iseconds)] Pruned backups older than ${RETENTION_DAYS} days"

# Optional: sync to Azure Blob (uncomment and configure)
# az storage blob upload \
#   --connection-string "${AZURE_STORAGE_CONNECTION_STRING}" \
#   --container-name "${AZURE_STORAGE_CONTAINER}" \
#   --name "db-backups/$(basename ${BACKUP_FILE})" \
#   --file "${BACKUP_FILE}"
# echo "[$(date -Iseconds)] Uploaded to Azure Blob"

echo "[$(date -Iseconds)] Done."
