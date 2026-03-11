# Azure デプロイ手順

このドキュメントでは、warikan-app を Azure にデプロイする手順を説明します。

## アーキテクチャ概要

```
┌─────────────────────┐     ┌──────────────────────────────┐
│   Azure Container   │     │  Azure App Service           │
│   Registry (ACR)    │────▶│  (Web App for Containers)    │
│   Docker イメージ保管  │     │  FastAPI アプリ               │
└─────────────────────┘     └──────────┬───────────────────┘
                                       │
                            ┌──────────▼───────────────────┐
                            │  Azure Database for MySQL    │
                            │  Flexible Server             │
                            └──────────────────────────────┘
```

## 前提条件

- Azure アカウント
- [Azure CLI](https://learn.microsoft.com/ja-jp/cli/azure/install-azure-cli) がインストール済み
- Docker がインストール済み（ローカルビルドの場合）

## 手順

### 1. Azure CLI にログイン

```bash
az login
```

### 2. リソースグループの作成

```bash
RESOURCE_GROUP="warikan-rg"
LOCATION="japaneast"

az group create --name $RESOURCE_GROUP --location $LOCATION
```

### 3. Azure Database for MySQL Flexible Server の作成

```bash
MYSQL_SERVER_NAME="warikan-mysql-server"
MYSQL_ADMIN_USER="warikanadmin"
MYSQL_ADMIN_PASSWORD="<強力なパスワードを設定>"  # 英大文字・小文字・数字・記号を含む8文字以上
MYSQL_DB_NAME="warikan_db"

# MySQL サーバーの作成
az mysql flexible-server create \
  --resource-group $RESOURCE_GROUP \
  --name $MYSQL_SERVER_NAME \
  --location $LOCATION \
  --admin-user $MYSQL_ADMIN_USER \
  --admin-password $MYSQL_ADMIN_PASSWORD \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 8.0.21 \
  --storage-size 20

# データベースの作成
az mysql flexible-server db create \
  --resource-group $RESOURCE_GROUP \
  --server-name $MYSQL_SERVER_NAME \
  --database-name $MYSQL_DB_NAME

# Azure サービスからのアクセスを許可
az mysql flexible-server firewall-rule create \
  --resource-group $RESOURCE_GROUP \
  --name $MYSQL_SERVER_NAME \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

### 4. Azure Container Registry (ACR) の作成

```bash
ACR_NAME="warikanacr"  # グローバルで一意な名前

az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true
```

### 5. Docker イメージのビルドとプッシュ

```bash
# ACR にログイン
az acr login --name $ACR_NAME

# ACR のログインサーバー名を取得
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)

# Docker イメージをビルド
cd backend
docker build -f Dockerfile.prod -t $ACR_LOGIN_SERVER/warikan-app:latest .

# ACR にプッシュ
docker push $ACR_LOGIN_SERVER/warikan-app:latest
```

### 6. Azure App Service の作成

```bash
APP_SERVICE_PLAN="warikan-plan"
WEBAPP_NAME="warikan-app"  # グローバルで一意な名前

# App Service プランの作成 (Linux)
az appservice plan create \
  --resource-group $RESOURCE_GROUP \
  --name $APP_SERVICE_PLAN \
  --is-linux \
  --sku B1

# ACR の認証情報を取得
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query "passwords[0].value" -o tsv)

# Web App for Containers の作成
az webapp create \
  --resource-group $RESOURCE_GROUP \
  --plan $APP_SERVICE_PLAN \
  --name $WEBAPP_NAME \
  --container-image-name $ACR_LOGIN_SERVER/warikan-app:latest \
  --container-registry-url https://$ACR_LOGIN_SERVER \
  --container-registry-user $ACR_USERNAME \
  --container-registry-password $ACR_PASSWORD
```

### 7. 環境変数（アプリケーション設定）の構成

```bash
az webapp config appsettings set \
  --resource-group $RESOURCE_GROUP \
  --name $WEBAPP_NAME \
  --settings \
    MYSQL_HOST="${MYSQL_SERVER_NAME}.mysql.database.azure.com" \
    MYSQL_PORT="3306" \
    MYSQL_USER="${MYSQL_ADMIN_USER}" \
    MYSQL_PASSWORD="${MYSQL_ADMIN_PASSWORD}" \
    MYSQL_DATABASE="${MYSQL_DB_NAME}" \
    SESSION_SECRET_KEY="$(openssl rand -hex 32)" \
    WEBSITES_PORT="8000"
```

> `WEBSITES_PORT` は App Service がコンテナのどのポートにトラフィックを転送するかを指定します。

### 8. デプロイの確認

```bash
# アプリの URL を確認
az webapp show --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME --query defaultHostName -o tsv

# ログを確認
az webapp log tail --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME
```

ブラウザで `https://<WEBAPP_NAME>.azurewebsites.net` にアクセスして動作確認してください。

---

## GitHub Actions による自動デプロイ (CI/CD)

### 必要な GitHub Secrets の設定

リポジトリの **Settings → Secrets and variables → Actions** で以下のシークレットを設定します。

| シークレット名 | 値 |
|---|---|
| `ACR_LOGIN_SERVER` | `<ACR名>.azurecr.io` |
| `ACR_USERNAME` | ACR の管理者ユーザー名 |
| `ACR_PASSWORD` | ACR の管理者パスワード |
| `AZURE_CREDENTIALS` | サービスプリンシパルの JSON（下記参照） |

### サービスプリンシパルの作成

```bash
az ad sp create-for-rbac \
  --name "warikan-github-actions" \
  --role contributor \
  --scopes /subscriptions/<SUBSCRIPTION_ID>/resourceGroups/$RESOURCE_GROUP \
  --json-auth
```

出力された JSON 全体を `AZURE_CREDENTIALS` シークレットとして登録します。

### ワークフローの動作

`.github/workflows/deploy-azure.yml` が設定済みです。`main` ブランチに push すると自動的に:

1. Docker イメージをビルド
2. ACR にプッシュ
3. App Service にデプロイ

---

## コスト目安（月額）

| リソース | SKU | 目安コスト |
|---|---|---|
| App Service | B1 (Basic) | 約 ¥2,000 |
| MySQL Flexible Server | Standard_B1ms (Burstable) | 約 ¥2,500 |
| Container Registry | Basic | 約 ¥700 |
| **合計** | | **約 ¥5,200/月** |

> 無料枠や従量課金により変動します。開発・テスト用途であれば、App Service の Free (F1) プランも検討できます（ただしカスタムコンテナは B1 以上が必要）。

---

## SSL/TLS について

Azure App Service はデフォルトで `https://<app-name>.azurewebsites.net` の SSL 証明書を提供します。カスタムドメインを使う場合は Azure が管理する無料証明書を利用できます。

```bash
# カスタムドメインの追加（オプション）
az webapp config hostname add \
  --resource-group $RESOURCE_GROUP \
  --webapp-name $WEBAPP_NAME \
  --hostname your-domain.com
```

## トラブルシューティング

### コンテナが起動しない場合

```bash
# コンテナのログを確認
az webapp log tail --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME

# SSH でコンテナに接続（デバッグ用）
az webapp ssh --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME
```

### MySQL に接続できない場合

- ファイアウォール設定で Azure サービスからのアクセスが許可されているか確認
- `MYSQL_HOST` が `<server-name>.mysql.database.azure.com` 形式になっているか確認
- MySQL の SSL 接続設定を確認（Azure MySQL はデフォルトで SSL を要求）

必要に応じて `db.py` の接続設定に SSL パラメータを追加:

```python
def _mysql_config() -> Dict[str, Any]:
    config = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "warikan_db"),
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": pymysql.cursors.DictCursor,
    }
    # Azure MySQL は SSL 接続を要求する
    if os.getenv("MYSQL_SSL", "").lower() == "true":
        config["ssl"] = {"ca": "/etc/ssl/certs/ca-certificates.crt"}
    return config
```
