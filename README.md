# warikan-app
EFREI Team Pacific

# 環境構築

## 前提
- Dockerをインストール＆起動済みであること

## 手順

プロジェクトのbackendフォルダに移動
```
cd warikan-app/backend
```

環境変数ファイルを作成（`.env.example` をコピーして値を編集）
```
cp .env.example .env
```

初期処理（`pyproject.toml` を変更した場合のみ）
```
poetry lock
```

Docker起動
```
docker-compose up --build
```

http://localhost:8000 にアクセス