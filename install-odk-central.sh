#!/bin/bash
#
# Install or upgrade ODK Central on the Hostinger server, in its own folder next to /opt/dimension.
# Central is a separate application with its own containers, database and .env. It stays out of this repository.
#
# Usage (from /opt/dimension):
#   ./install-odk-central.sh you@example.org        first install; the email is Central's SYSADMIN_EMAIL
#   ./install-odk-central.sh                        upgrade: backs up, then moves to CENTRAL_VERSION below
#
# Read Central's release notes before upgrading: https://github.com/getodk/central/releases

set -euo pipefail
cd "$(dirname "$0")"
PROJECT_DIR="$PWD"

CENTRAL_VERSION="${CENTRAL_VERSION:-v2026.3.1}"
CENTRAL_DIR="${CENTRAL_DIR:-/opt/odk-central}"
ODK_DOMAIN="${ODK_DOMAIN:-odk.tamris.org}"
ODK_WEB_PORT="${ODK_WEB_PORT:-8092}"
MIN_FREE_GB=15
SYSADMIN_EMAIL="${1:-}"

# Checks ---------------------------------------------------------------------------
COMPOSE_VERSION="$(docker compose version --short)"
if [ "$(printf '%s\n' 2.24.4 "${COMPOSE_VERSION#v}" | sort -V | head -n1)" != 2.24.4 ]; then
    echo "Docker Compose $COMPOSE_VERSION is too old: 2.24.4 or newer is needed." >&2
    exit 1
fi

FIRST_INSTALL=no
[ -d "$CENTRAL_DIR/.git" ] || FIRST_INSTALL=yes

if [ "$FIRST_INSTALL" = yes ]; then
    if [ -z "$SYSADMIN_EMAIL" ]; then
        echo "First install: give the administrator email.  ./install-odk-central.sh you@example.org" >&2
        exit 1
    fi
    FREE_GB="$(df -BG --output=avail "$(dirname "$CENTRAL_DIR")" | tail -n1 | tr -dc 0-9)"
    if [ "$FREE_GB" -lt "$MIN_FREE_GB" ]; then
        echo "Only ${FREE_GB} GB free on the disk: at least ${MIN_FREE_GB} GB is needed." >&2
        exit 1
    fi
    if ss -ltn | grep -q ":$ODK_WEB_PORT "; then
        echo "Port $ODK_WEB_PORT is in use. Choose another: ODK_WEB_PORT=8093 ./install-odk-central.sh $SYSADMIN_EMAIL" >&2
        echo "and change proxy_pass in docker/nginx-odk.conf to match." >&2
        exit 1
    fi
fi

# Code -----------------------------------------------------------------------------
umask 022   # Central's containers read these files as other users.
if [ "$FIRST_INSTALL" = yes ]; then
    echo "Downloading ODK Central $CENTRAL_VERSION to $CENTRAL_DIR ..."
    git clone --branch "$CENTRAL_VERSION" https://github.com/getodk/central "$CENTRAL_DIR"
else
    cd "$CENTRAL_DIR"
    if docker compose ps --status running --services 2>/dev/null | grep -qx postgres14; then
        "$PROJECT_DIR/backup-odk-central.sh" before_upgrade >/dev/null
    fi
    echo "Moving ODK Central to $CENTRAL_VERSION ..."
    git fetch --tags origin
    git checkout "$CENTRAL_VERSION"
fi
cd "$CENTRAL_DIR"
git submodule update --init --recursive

# Settings -------------------------------------------------------------------------
if [ ! -f .env ]; then
    cp .env.template .env
    sed -i -e "s|^DOMAIN=.*|DOMAIN=$ODK_DOMAIN|" \
           -e "s|^SYSADMIN_EMAIL=.*|SYSADMIN_EMAIL=$SYSADMIN_EMAIL|" \
           -e "s|^SSL_TYPE=.*|SSL_TYPE=upstream|" .env
    printf '\n# Port on 127.0.0.1 that the host nginx forwards %s to.\nODK_WEB_PORT=%s\n' "$ODK_DOMAIN" "$ODK_WEB_PORT" >> .env
    chmod 600 .env
fi
cp "$PROJECT_DIR/docker/odk-central.override.yml" docker-compose.override.yml

# Refuse to start if Central would take any public port, such as the host nginx's 80 and 443.
docker compose config --format json | python3 -c '
import json, sys
ports = [p for s in json.load(sys.stdin)["services"].values() for p in s.get("ports", [])]
public = [p for p in ports if p.get("host_ip") != "127.0.0.1"]
if public or len(ports) != 1:
    sys.exit(f"Refusing to start: expected one port on 127.0.0.1, got {ports}")
'

# Build and start ------------------------------------------------------------------
echo "Building ODK Central (this takes several minutes; other sites keep running) ..."
docker compose pull --ignore-buildable
docker compose build --pull
docker compose stop
docker compose up -d

echo
docker compose ps
echo
echo "ODK Central $CENTRAL_VERSION is up. Check from the server:  curl -sI -H 'Host: $ODK_DOMAIN' http://127.0.0.1:\$(grep ^ODK_WEB_PORT= $CENTRAL_DIR/.env | cut -d= -f2)/"
