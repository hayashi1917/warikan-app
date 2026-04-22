# Backend directory guide

## ディレクトリ構成

- `app/main.py`: FastAPI のエントリポイント。ミドルウェア登録とルーター組み込みを担当。
- `app/api/`: ルーティング層。HTTP 入出力（リクエスト検証、レスポンス整形）に集中。
  - `app/api/routes/`: 機能単位のルーター。
- `app/services/`: ユースケース層。DB アクセスや外部 API 連携など、画面に依存しない処理を担当。
- `app/db/`: DB 接続とスキーマ初期化。
- `app/schemas/`: Pydantic による入力検証スキーマ。

## 設計方針

- フロントエンドとバックエンドの疎結合を重視し、画面遷移の詳細は API レスポンス (`redirect_url`) として返却。
- ルート層は「HTTP の変換」に専念し、業務ロジックはサービス層へ集約。
- DB に関する実装詳細はサービス層以下に閉じ込め、将来の UI 変更時の影響範囲を最小化。

## Render デプロイ

このアプリは PostgreSQL を使用します。Render では先に PostgreSQL を作成し、Web Service には PostgreSQL の Internal Database URL を `DATABASE_URL` として設定してください。

### Web Service 設定

- Runtime: `Python 3`
- Build Command: `pip install .`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 環境変数

- `DATABASE_URL`: Render PostgreSQL の Internal Database URL
- `SESSION_SECRET_KEY`: 本番用の長いランダム文字列

アプリ起動時に `app/db/db.py` の `ensure_schema()` が必要なテーブルを自動作成します。
