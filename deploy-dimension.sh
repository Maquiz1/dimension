#!/bin/bash
#
# Deploy DIMENSION on the Hostinger server (/opt/dimension), same steps as deploy-penplus.sh:
#   1. back up the database
#   2. build the new image while the old site keeps serving
#   3. migrate the database
#   4. switch the containers to the new code
#
# Usage:  git pull && ./deploy-dimension.sh
# First time: ./deploy-dimension.sh --first   (also loads the clinics, then asks for an admin account)
# Backups go to $BACKUP_DIR (default ~/backups/dimension). Copy them off the server regularly.

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
    echo "Missing .env. Run: cp .env.production.example .env  and fill in the values." >&2
    exit 1
fi
if grep -qE '^(DJANGO_SECRET_KEY|POSTGRES_PASSWORD)=change-me$' .env; then
    echo "Set DJANGO_SECRET_KEY and POSTGRES_PASSWORD in .env first (openssl rand -base64 48)." >&2
    exit 1
fi

# 1. Backups -------------------------------------------------------------------
if docker compose ps --status running --services 2>/dev/null | grep -qx dimension-db; then
    DB_BACKUP="$(./backup-dimension.sh before_deploy | tail -n1)"
else
    echo "Database container is not running yet (first deployment?): skipping backup."
    DB_BACKUP=""
fi

# 2. Build ---------------------------------------------------------------------
echo "Building the new image (the current site keeps running)..."
docker compose build dimension-web

# 3. Migrate -------------------------------------------------------------------
echo "Starting the database if needed..."
docker compose up -d dimension-db
for i in $(seq 1 30); do
    if docker compose exec -T dimension-db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then break; fi
    sleep 2
done

echo "Migrations that will run:"
docker compose run --rm dimension-web python manage.py migrate --plan
echo "Running database migrations..."
docker compose run --rm dimension-web python manage.py migrate --noinput

# 4. Switch --------------------------------------------------------------------
echo "Switching to the new code..."
docker compose up -d

if [ "${1:-}" = "--first" ]; then
    if [ -s data_dictionary/DIMENSION_Data_Dictionary_v0.1.xlsx ]; then
        echo "First deployment: loading the clinics..."
        docker compose exec -T dimension-web python manage.py load_sites
    else
        echo "Data dictionary not on the server yet, so the clinics were not loaded."
        echo "Run ./copy-dictionary-to-server.sh on your computer, then here:"
        echo "  docker compose exec dimension-web python manage.py load_sites"
    fi
    echo "Create the first administrator account:"
    docker compose exec dimension-web python manage.py createsuperuser
fi

echo
docker compose ps
echo
echo "Deployment completed. Check from the server:  curl -sI http://127.0.0.1:\${WEB_PORT:-8091}/admin/login/"
if [ -n "$DB_BACKUP" ]; then
    echo "Backup from before this deployment: $DB_BACKUP"
    echo "To roll back the code:    git checkout \$(cat ${DB_BACKUP%_db.dump}_commit.txt) && docker compose build dimension-web && docker compose up -d"
    echo "To restore the database:  ./restore-dimension.sh $DB_BACKUP"
fi
