#!/usr/bin/env bash
set -e

echo "Waiting for database..."
python - <<'PY'
import os
import time
import pymysql
from urllib.parse import urlparse

url = os.environ.get("DATABASE_URL", "")
u = urlparse(url.replace("mysql+pymysql", "mysql"))

user = u.username
password = u.password
host = u.hostname
port = u.port or 3306
db = u.path.lstrip("/") if u.path else None

for i in range(30):
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=db,
            port=port
        )
        conn.close()
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