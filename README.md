# FairShare

旅行や短期滞在のグループ精算を、通貨換算と承認フロー込みで管理できる割り勘Webアプリです。

グループ作成、支払い登録、メンバーごとの承認、外貨の日本円換算、承認済み支払いをもとにした最小限の精算計算までを一つの画面で扱えます。

## 開発した背景

既存の割り勘アプリでは、「個別に誰がいくら立て替えたか」「グループの誰かが出鱈目な情報を入力してきたらどうするか」「外貨を日本円でどう精算するか」が曖昧になりやすいと感じました。

このアプリは、グループ内のお金のやり取りを記録し、関係者全員が承認した支払いだけを精算対象にすることで、後から揉めにくい透明な割り勘体験を目指して開発しました。

## アプリ公開URL
https://warikan-app-03e3.onrender.com/

## 目次

- [開発した背景](#開発した背景)
- [アプリ公開URL](#アプリ公開url)
- [スクリーンショット](#スクリーンショット)
- [使用技術について](#使用技術について)
- [環境構築手順](#環境構築手順)
- [こだわり／工夫した点](#こだわり工夫した点)
- [API一覧](#api一覧)
- [今後の展望](#今後の展望)

## スクリーンショット

- グループ作成／参加画面/ログイン
  <img width="568" height="636" alt="スクリーンショット 2026-04-23 16 20 28" src="https://github.com/user-attachments/assets/7591e14d-b0ec-45c0-8794-34592972b262" />

- 支払い登録画面
  <img width="611" height="745" alt="スクリーンショット 2026-04-23 16 20 53" src="https://github.com/user-attachments/assets/d1f20ba6-8966-48d9-8ef4-0c37fb6fbd19" />

- 未承認／承認済み支払い一覧
  <img width="475" height="575" alt="スクリーンショット 2026-04-23 16 21 20" src="https://github.com/user-attachments/assets/6c539c05-5573-4034-a70b-c8e31529fcf9" />

- 最小化された精算結果画面
  <img width="527" height="578" alt="スクリーンショット 2026-04-23 16 21 56" src="https://github.com/user-attachments/assets/cb3c8ce8-7a0c-463a-a754-158c784d9bb3" />

## 使用技術について

### フロントエンド

| 技術 | バージョン / 備考 |
| --- | --- |
| HTML | Jinja2テンプレートで描画 |
| CSS | 素のCSS |
| JavaScript | 素のJavaScript |
| Jinja2 | 3.1.6以上、4.0.0未満 |

### バックエンド

| 技術 | バージョン / 備考 |
| --- | --- |
| Python | 3.12以上 |
| FastAPI | 0.135.1以上、0.136.0未満 |
| Uvicorn | 0.41.0以上、0.42.0未満 |
| Pydantic | 2.12.5以上、3.0.0未満 |

### データベース

| 技術 | バージョン / 備考 |
| --- | --- |
| PostgreSQL | `DATABASE_URL`で接続 |

### 外部API

| API | 用途 |
| --- | --- |
| Frankfurter API | 外貨から日本円への為替レート取得 |

### インフラ・開発環境

| 技術 | バージョン / 備考 |
| --- | --- |
| Docker | `Dockerfile.local`、`Dockerfile.aws`を用意 |
| Docker Compose | `docker-compose.yml`を用意 |
| Poetry | 依存関係管理 |

## 環境構築手順

### 1. リポジトリをクローン

```bash
git clone <repository-url>
cd warikan-app
```

### 2. 環境変数を設定

```bash
cp .env.example .env.local
```

`.env.local`に以下を設定します。

```env
DATABASE_URL="postgresql://postgres:password@127.0.0.1:5432/warikan_app"
SESSION_SECRET_KEY="replace-with-a-random-secret"
```

### 3. Dockerで起動

```bash
docker compose up --build
```

起動後、以下にアクセスします。

```text
http://localhost:8000
```

### 4. Dockerを使わずに起動する場合

PostgreSQLをローカルで起動したうえで、依存関係をインストールします。

```bash
poetry install
```

アプリを起動します。

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

起動後、以下にアクセスします。

```text
http://localhost:8000
```

## こだわり／工夫した点

- 支払い関係者全員が承認した支払いだけを精算対象にし、未確認の立て替えが勝手に計算へ入らないようにしました。
- 支払い登録時点の為替レートを保存し、後日のレート変動によって過去の精算結果が変わらないようにしました。
- 精算ロジックではユーザーごとの差額を集計し、支払う人と受け取る人をマッチングすることで、お金の移動回数を抑えています。

### ER図
<img width="1448" height="1086" alt="ChatGPT Image 2026年4月23日 16_23_28" src="https://github.com/user-attachments/assets/b68f9dd6-7b2f-4e73-9e5b-5639b07dfd95" />

## API一覧

| メソッド | パス | 概要 |
| --- | --- | --- |
| GET | `/` | トップページ表示 |
| GET | `/about` | Aboutページ表示 |
| GET | `/register/start` | グループ作成・参加・ログイン画面表示 |
| GET | `/register/me` | セッション上のログインユーザー情報取得 |
| POST | `/register/register_group` | グループ作成とリーダーユーザー登録 |
| POST | `/register/join_group` | 既存グループへの参加 |
| POST | `/register/login` | ログイン |
| GET | `/payment/` | 支払い管理画面表示 |
| GET | `/payment/members` | グループメンバー一覧取得 |
| POST | `/payment/create` | 支払い登録 |
| DELETE | `/payment/{payment_id}` | 支払い削除 |
| POST | `/payment/authenticate` | 支払い承認 |
| GET | `/payment/list` | グループ内の支払い一覧取得 |
| GET | `/payment/settlements` | 承認済み支払いをもとに精算結果を取得 |

## 今後の展望

- ユーザー招待リンクの発行
- 精算完了ステータスの管理
- テストコードの拡充
- 日本語版の実装
