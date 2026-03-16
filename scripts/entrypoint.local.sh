#!/usr/bin/env bash
set -e
# ↑ set -e : どこかで失敗したら即終了。
#   失敗してるのに “成功したように見える” のが一番危険なので、
#   起動スクリプトでは基本これを付ける。

echo "Waiting for MySQL..."
python - <<'PY'
import os, time
import pymysql

url = os.environ.get("DATABASE_URL", "")
# ↑ 接続先をハードコードしない（設定は環境変数から）。

# mysql+pymysql://user:pass@db:3306/name?charset=utf8mb4 を雑に分解
from urllib.parse import urlparse
u = urlparse(url.replace("mysql+pymysql", "mysql"))
# ↑ urlparse は scheme の形式が素直な方が扱いやすいので置換している。
#   （より堅牢にするなら SQLAlchemy の make_url を使う）

user = u.username
password = u.password
host = u.hostname
port = u.port or 3306
db = u.path.lstrip("/") if u.path else None

for i in range(60):
    try:
        conn = pymysql.connect(host=host, user=user, password=password, database=db, port=port)
        conn.close()
        print("MySQL is up!")
        break
    except Exception:
        time.sleep(1)
# ↑ “DBが接続できる状態になるまで待つ”。
#   healthcheck + depends_on を書いていても、
#   実務ではネットワーク遅延や初期化で一瞬失敗することがあるため二重化している。
#   （どちらか片方でも良いが、学習用には確実に動く方がよい）

else:
    raise SystemExit("MySQL not ready")
PY

# マイグレーション（Alembic使うならここで）
# alembic upgrade head
# ↑ DBスキーマを “起動時に最新化” したい場合にここへ置く。
#   ・チーム開発で環境差が出にくい
#   ・ただし本番では運用方針次第（起動時自動migrationを嫌う現場もある）

echo "Starting FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# ↑ exec を使う理由：
#   シェルを置き換えてuvicornをPID1にする → SIGTERMなどが素直に届く（停止が綺麗）
# ↑ --host 0.0.0.0 :
#   コンテナ外（ホスト）からアクセスできるようにする。127.0.0.1 だと内部限定になる。
# ↑ --reload :
#   開発用。ファイル変更を検知して自動再起動。
#   本番では絶対に外す（無駄＆危険）。