#!/bin/bash
#
# Back up DIMENSION on the server: database and the code version. Run in /opt/dimension.
# Also used by deploy-dimension.sh and restore-dimension.sh before they change anything.
#
# Usage:  ./backup-dimension.sh [label]        e.g. ./backup-dimension.sh before_import
# Files:  $BACKUP_DIR/<date>_<label>_db.dump, _commit.txt   (default BACKUP_DIR ~/backups/dimension)
# Old backups are deleted after KEEP_DAYS (default 30). Copy backups off the server regularly.
#
# Daily at 01:40 (crontab -e):
#   40 1 * * * cd /opt/dimension && ./backup-dimension.sh daily >> ~/backups/dimension/backup.log 2>&1

set -euo pipefail
cd "$(dirname "$0")"

LABEL="${1:-manual}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/dimension}"
KEEP_DAYS="${KEEP_DAYS:-30}"
PREFIX="$BACKUP_DIR/$(date +%F_%H%M)_${LABEL}"

mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR"

if ! docker compose ps --status running --services 2>/dev/null | grep -qx dimension-db; then
    echo "The database container is not running: nothing to back up." >&2
    exit 1
fi

echo "Backing up the database to ${PREFIX}_db.dump ..." >&2
docker compose exec -T dimension-db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "${PREFIX}_db.dump"
if [ ! -s "${PREFIX}_db.dump" ]; then
    echo "Database backup is empty." >&2
    rm -f "${PREFIX}_db.dump"
    exit 1
fi

git rev-parse HEAD > "${PREFIX}_commit.txt" 2>/dev/null || true
chmod 600 "${PREFIX}"_*

find "$BACKUP_DIR" -maxdepth 1 -type f -name '20*_*' -mtime +"$KEEP_DAYS" -delete

echo "Backup done: ${PREFIX}_db.dump ($(du -h "${PREFIX}_db.dump" | cut -f1))" >&2
# Progress goes to stderr; stdout is only the database file, so other scripts can read it.
echo "${PREFIX}_db.dump"
