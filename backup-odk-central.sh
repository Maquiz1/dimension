#!/bin/bash
#
# Back up ODK Central's database (users, forms, submissions and attachments) and its secrets volume.
# Tablet submissions that Django has not pulled yet exist only in Central, so this matters as much as the Django backup.
#
# Usage:  ./backup-odk-central.sh [label]
# Files:  $BACKUP_DIR/<date>_<label>_odk.dump, _odk_secrets.tar.gz   (default BACKUP_DIR ~/backups/odk-central)
# Old backups are deleted after KEEP_DAYS (default 30). Copy backups off the server regularly.
#
# Daily at 01:50 (crontab -e):
#   50 1 * * * /opt/dimension/backup-odk-central.sh daily >> ~/backups/odk-central/backup.log 2>&1

set -euo pipefail

CENTRAL_DIR="${CENTRAL_DIR:-/opt/odk-central}"
LABEL="${1:-manual}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/odk-central}"
KEEP_DAYS="${KEEP_DAYS:-30}"
PREFIX="$BACKUP_DIR/$(date +%F_%H%M)_${LABEL}"

mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR"
cd "$CENTRAL_DIR"

if ! docker compose ps --status running --services 2>/dev/null | grep -qx postgres14; then
    echo "Central's database container is not running: nothing to back up." >&2
    exit 1
fi

echo "Backing up Central's database to ${PREFIX}_odk.dump ..." >&2
docker compose exec -T postgres14 pg_dump -U odk -d odk -Fc > "${PREFIX}_odk.dump"
if [ ! -s "${PREFIX}_odk.dump" ]; then
    echo "Central database backup is empty." >&2
    rm -f "${PREFIX}_odk.dump"
    exit 1
fi

# Enketo's keys, needed to keep existing web form links after a restore.
echo "Backing up Central's secrets to ${PREFIX}_odk_secrets.tar.gz ..." >&2
docker compose run --rm --no-deps -T --entrypoint tar secrets czf - -C /etc/secrets . > "${PREFIX}_odk_secrets.tar.gz"
chmod 600 "${PREFIX}"_*

find "$BACKUP_DIR" -maxdepth 1 -type f -name '20*_*' -mtime +"$KEEP_DAYS" -delete

echo "Backup done: ${PREFIX}_odk.dump ($(du -h "${PREFIX}_odk.dump" | cut -f1))" >&2
echo "${PREFIX}_odk.dump"
