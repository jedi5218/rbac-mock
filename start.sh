#!/bin/bash
set -e

echo "Running database migrations..."
cd /app
alembic upgrade head

echo "Migrations complete. Starting services..."
exec supervisord -c /etc/supervisor/conf.d/app.conf
