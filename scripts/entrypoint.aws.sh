#!/usr/bin/env bash
set -e

echo "Waiting for database..."
python - <<'PY'
import os
import time

import psycopg

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL is not set")

for i in range(30):
    try:
        with psycopg.connect(database_url, connect_timeout=3):
            pass
        print("Database is up!")
        break
    except Exception as e:
        print(f"Waiting... ({i+1}/30)")
        time.sleep(2)
else:
    raise SystemExit("Database not ready")
PY

# 必要なら
# alembic upgrade head

echo "Starting FastAPI (aws)..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
