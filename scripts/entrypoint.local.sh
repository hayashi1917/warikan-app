#!/usr/bin/env bash
set -e

echo "Waiting for PostgreSQL..."
python - <<'PY'
import os
import time

import psycopg

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL is not set")

for i in range(60):
    try:
        with psycopg.connect(database_url, connect_timeout=3):
            pass
        print("PostgreSQL is up!")
        break
    except Exception as exc:
        print(f"Waiting... ({i + 1}/60): {exc}")
        time.sleep(1)
else:
    raise SystemExit("PostgreSQL not ready")
PY

# マイグレーション（Alembicを使う場合はここで実行）
# alembic upgrade head

echo "Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
