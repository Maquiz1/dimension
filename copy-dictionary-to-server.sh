#!/bin/bash
#
# Copy the data dictionary to the server. It is kept out of git, and load_sites reads the clinics from it.
# Run on your computer (not on the server).
#
# Usage:  ./copy-dictionary-to-server.sh [user@server]
# Default: root@31.97.187.66

set -euo pipefail
cd "$(dirname "$0")"

FILE=data_dictionary/DIMENSION_Data_Dictionary_v0.1.xlsx
SERVER="${1:-root@31.97.187.66}"
REMOTE_DIR=/opt/dimension/data_dictionary

if [ ! -s "$FILE" ]; then
    echo "Not found: $FILE" >&2
    exit 1
fi

echo "Copying $FILE to $SERVER:$REMOTE_DIR ..."
ssh "$SERVER" "mkdir -p $REMOTE_DIR"
scp "$FILE" "$SERVER:$REMOTE_DIR/$(basename "$FILE").part"
# World-readable because the container runs as an unprivileged user. It holds variables and clinics, no participant data.
ssh "$SERVER" "chmod 755 $REMOTE_DIR && chmod 644 $REMOTE_DIR/$(basename "$FILE").part && mv $REMOTE_DIR/$(basename "$FILE").part $REMOTE_DIR/$(basename "$FILE")"

echo
echo "Done. On the server run:  cd /opt/dimension && docker compose exec dimension-web python manage.py load_sites"
