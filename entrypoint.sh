#!/bin/bash
set -e

echo "Waiting for database to be ready..."
until pg_isready -h db -p 5432 -U postgres; do
  echo "Database not ready yet, retrying in 2 seconds..."
  sleep 2
done

echo "Running Alembic migrations..."
alembic upgrade head
echo "Migrations complete. Starting server..."

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
