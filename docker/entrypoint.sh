#!/bin/sh
# Wait for PostgreSQL, then run the container's command.
# Migrations are run by deploy-dimension.sh, once, before the containers switch to new code.
set -e

python - <<'EOF'
import os, socket, sys, time
host, port = os.environ.get('POSTGRES_HOST', 'dimension-db'), int(os.environ.get('POSTGRES_PORT', '5432'))
for _ in range(60):
    try:
        socket.create_connection((host, port), timeout=2).close()
        sys.exit(0)
    except OSError:
        time.sleep(1)
sys.exit(f'Database {host}:{port} is not reachable.')
EOF

exec "$@"
