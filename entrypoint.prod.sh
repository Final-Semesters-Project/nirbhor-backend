#!/bin/bash
set -e

echo "Running migrations..."
alembic upgrade head
echo "Starting server..."

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips '*' --workers 1 --no-access-log
