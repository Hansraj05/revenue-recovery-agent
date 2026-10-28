#!/usr/bin/env bash
set -e

echo "Applying database migrations..."
alembic upgrade head

# Render has no free Background Worker plan, so the Celery worker runs inside
# this same service. The loop restarts it if it ever crashes.
(
  while true; do
    celery -A app.tasks.celery_app worker --loglevel=info --pool=solo
    echo "Celery worker exited - restarting in 3s..."
    sleep 3
  done
) &

echo "Starting API..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-10000}"