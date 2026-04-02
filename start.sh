#!/bin/bash
set -e

cd /app

echo "Waiting for database to be ready..."
for i in $(seq 1 30); do
    if alembic upgrade head 2>&1; then
        echo "Migrations complete. Starting services..."
        exec supervisord -c /etc/supervisor/conf.d/app.conf
    fi
    echo "Migration attempt $i failed, retrying in 2s..."
    sleep 2
done

echo "ERROR: Could not connect to database after 30 attempts"
exit 1
