# バックエンド コードレビュー結果

レビュー日: 2026-03-09

## 1. フロントエンドとバックエンドの疎結合

### 良い点
- APIレスポンスに `redirect_url` を返し、画面遷移をフロント側に委ねている設計
- サービス層がDB操作を隠蔽し、ルートハンドラからSQLが見えない構造
- `api.py` でルーターを集約しており、エントリポイント (`main.py`) がシンプル

### 問題点

#### [重要] テンプレートHTML内にサーバーサイドのテンプレート変数が埋め込まれている
`compute.html` で Jinja2 テンプレート構文が使われている:
```javascript
const MEMBER_NAMES = {{ member_names | tojson }};
```
APIから `GET /payment/members?group_id=xxx` のようなエンドポイントでメンバー一覧を取得する方式にすれば、完全に疎結合になる。

#### [重要] セッションとlocalStorageの二重管理
認証情報がサーバーサイドセッション (`request.session`) とクライアントのlocalStorage の両方に保存されている。不整合のリスクがあるため、どちらか一方に統一すべき。

#### [軽微] テンプレートHTMLがバックエンド内に配置されている
疎結合を目指すなら、フロントエンドは別ディレクトリ（例: `frontend/`）に分離し、バックエンドは純粋なAPIサーバーとして機能させるのが望ましい。

---

## 2. わかりやすい変数名と日本語コメント

### 良い点
- サービス層の各関数に日本語コメントが付いている
- `api.py` のモジュールdocstringが丁寧で設計意図が明確
- DB操作関数名が動詞+名詞で意味が分かりやすい

### 問題点

#### [重要] HTMLテンプレート内のid/placeholderが紛らわしい
`start.html` にて:
```html
<input type="text" name="group_name" id="group_id" placeholder="GroupID">
<input type="text" name="user_name" id="user_id" placeholder="User_ID">
```
`name="group_name"` なのに `id="group_id"`、`placeholder="GroupID"` — 「グループ名」なのか「グループID」なのか混乱する。

#### [軽微] docstringが無いルートハンドラがある
`join_group_post` と `login_post` にはdocstringがない。`register_group_post` にはあるので統一すべき。

#### [軽微] テンプレートファイル内の言語が混在
`start.html` は `lang="en"` でUI文言が英語、`compute.html` は `lang="ja"` で日本語混在。

---

## 3. バグの有無

### [致命的] `create_group_with_leader` のレースコンディション
`groups` テーブルの `group_name` に `UNIQUE` 制約がないため、同名グループが作成されうる。
**修正案**: `groups` テーブルに `UNIQUE(group_name)` を追加し、`IntegrityError` をキャッチする。

### [重要] `list_payments` と `settlements` エンドポイントに認証チェックがない
`group_id` をクエリパラメータとして受け取るだけで、セッション認証を一切チェックしていない。任意のgroup_idを指定することで、他グループの支払い情報を閲覧できてしまう。

### [重要] `authenticate` エンドポイントでもgroup_idがクエリパラメータ
セッションの `group_id` と照合せずにクエリパラメータの `group_id` をそのまま使用しているため、他グループの支払いを承認できてしまう。

### [重要] `create_payment` で `exchange_rate` がスキーマと二重に存在
`PaymentCreateRequest` に `exchange_rate` フィールドがあるが、サーバー側で計算したレートを使っている。クライアントが送信した `exchange_rate` は無視されるため、スキーマ定義が誤解を招く。

### [中程度] DB接続がリクエストごとに新規作成される
`mysql_connection()` はリクエストのたびに `pymysql.connect()` を呼ぶ。コネクションプーリングがないため、高負荷時にDB接続数が枯渇する可能性がある。

### [軽微] `create_payment` で例外時にコネクションがロールバックされない
明示的な `conn.rollback()` が安全。

---

## 4. ファイル構成・ディレクトリ構成

### 良い点
- `api/routes/`, `services/`, `schemas/`, `auth/`, `db/` と責務ごとにディレクトリ分けされている
- `api.py` でルーター集約しているのは見通しが良い

### 問題点

#### [重要] `services/` に機能が被ったファイルが3つある
| ファイル | 内容 |
|---|---|
| `services/services.py` | 支払い作成・削除・承認・一覧・為替レート |
| `services/payments.py` | 精算計算ロジック |
| `services/payment.py` | レガシーのpandas版精算ロジック（未使用） |

整理案:
- `services/payment.py` (レガシー) → 削除
- `services/services.py` → `services/payment_service.py` にリネーム
- `services/payments.py` → `services/settlement.py` にリネーム

#### [重要] レガシーテンプレートが残っている
以下のテンプレートは `start.html` に置き換え済みで未使用:
- `templates/login.html`
- `templates/register_group.html`
- `templates/join_group.html`

#### [中程度] `db.py` に不要なインポートが残っている
`hashlib`, `hmac`, `passlib` は `auth.py` に既にあり、`db.py` には不要。

#### [軽微] `schemas.py` に重複スキーマがある
`GroupCreateRequest` と `UserCreateRequest` は完全に同じフィールド定義。`RegisterRequest` と `LoginRequest` も同じ構造。

---

## 総合評価

| 観点 | 評価 | 概要 |
|---|---|---|
| 疎結合 | **B** | JSON APIでの画面遷移制御は良いが、Jinja2テンプレート依存・セッションとlocalStorageの二重管理が課題 |
| 変数名・コメント | **B+** | サービス層のコメントは丁寧。HTMLのid/name/placeholderの不一致が目立つ |
| バグ | **C** | group_nameのUNIQUE制約欠如、認証チェック漏れは早急に修正が必要 |
| ファイル構成 | **B-** | 基本構造は良いが、レガシーファイル残存・services内のファイル名被りが混乱を招く |
