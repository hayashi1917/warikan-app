# AWS デプロイ手順

このドキュメントでは、warikan-app を AWS にデプロイする手順を説明します。

## アーキテクチャ概要

```
┌─────────────────────┐     ┌──────────────────────────────┐
│  Amazon ECR         │     │  AWS App Runner              │
│  Docker イメージ保管   │────▶│  FastAPI アプリ                │
└─────────────────────┘     └──────────┬───────────────────┘
                                       │ (VPC Connector)
                            ┌──────────▼───────────────────┐
                            │  Amazon RDS for MySQL        │
                            └──────────────────────────────┘
```

## 前提条件

- AWS アカウント
- [AWS CLI v2](https://docs.aws.amazon.com/ja_jp/cli/latest/userguide/getting-started-install.html) がインストール・設定済み
- Docker がインストール済み（ローカルビルドの場合）

## 手順

### 1. AWS CLI の設定

```bash
aws configure
# AWS Access Key ID: <あなたのアクセスキー>
# AWS Secret Access Key: <あなたのシークレットキー>
# Default region name: ap-northeast-1
# Default output format: json
```

### 2. 変数の設定

```bash
AWS_REGION="ap-northeast-1"
APP_NAME="warikan-app"
MYSQL_ADMIN_USER="warikanadmin"
MYSQL_ADMIN_PASSWORD="<強力なパスワードを設定>"  # 英大文字・小文字・数字・記号を含む8文字以上
MYSQL_DB_NAME="warikan_db"
```

### 3. VPC の準備

App Runner から RDS にプライベート接続するために VPC が必要です。デフォルト VPC を使うか、新規作成します。

```bash
# デフォルト VPC の ID を取得
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" --output text)

# サブネット ID を取得（2つ以上必要）
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[*].SubnetId" --output text)

echo "VPC: $VPC_ID"
echo "Subnets: $SUBNET_IDS"
```

### 4. RDS 用セキュリティグループの作成

```bash
# セキュリティグループを作成
SG_ID=$(aws ec2 create-security-group \
  --group-name warikan-db-sg \
  --description "Security group for warikan RDS" \
  --vpc-id $VPC_ID \
  --query "GroupId" --output text)

# MySQL ポート (3306) を VPC 内からのアクセスに開放
VPC_CIDR=$(aws ec2 describe-vpcs \
  --vpc-ids $VPC_ID \
  --query "Vpcs[0].CidrBlock" --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 3306 \
  --cidr $VPC_CIDR
```

### 5. Amazon RDS for MySQL の作成

```bash
# DB サブネットグループの作成
SUBNET_ARR=($SUBNET_IDS)
aws rds create-db-subnet-group \
  --db-subnet-group-name warikan-db-subnet \
  --db-subnet-group-description "Subnet group for warikan DB" \
  --subnet-ids ${SUBNET_ARR[@]}

# RDS インスタンスの作成
aws rds create-db-instance \
  --db-instance-identifier warikan-mysql \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version "8.0" \
  --master-username $MYSQL_ADMIN_USER \
  --master-user-password $MYSQL_ADMIN_PASSWORD \
  --allocated-storage 20 \
  --db-name $MYSQL_DB_NAME \
  --vpc-security-group-ids $SG_ID \
  --db-subnet-group-name warikan-db-subnet \
  --no-publicly-accessible \
  --storage-type gp3

# 作成完了を待つ（数分かかります）
aws rds wait db-instance-available --db-instance-identifier warikan-mysql

# RDS エンドポイントを取得
RDS_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier warikan-mysql \
  --query "DBInstances[0].Endpoint.Address" --output text)

echo "RDS Endpoint: $RDS_ENDPOINT"
```

### 6. Amazon ECR リポジトリの作成

```bash
# ECR リポジトリを作成
aws ecr create-repository \
  --repository-name $APP_NAME \
  --region $AWS_REGION

# ECR レジストリ URI を取得
ECR_URI=$(aws ecr describe-repositories \
  --repository-names $APP_NAME \
  --query "repositories[0].repositoryUri" --output text)

echo "ECR URI: $ECR_URI"
```

### 7. Docker イメージのビルドとプッシュ

```bash
# ECR にログイン
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  $(echo $ECR_URI | cut -d'/' -f1)

# Docker イメージをビルド
cd backend
docker build -f Dockerfile.prod -t $ECR_URI:latest .

# ECR にプッシュ
docker push $ECR_URI:latest
```

### 8. App Runner 用の VPC Connector を作成

```bash
SUBNET_ARR=($SUBNET_IDS)

CONNECTOR_ARN=$(aws apprunner create-vpc-connector \
  --vpc-connector-name warikan-vpc-connector \
  --subnets ${SUBNET_ARR[@]:0:2} \
  --security-groups $SG_ID \
  --query "VpcConnector.VpcConnectorArn" --output text)

echo "VPC Connector: $CONNECTOR_ARN"
```

### 9. App Runner 用 IAM ロールの作成

```bash
# ECR アクセス用ロール
cat > trust-policy.json << 'POLICY'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "build.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY

aws iam create-role \
  --role-name warikan-apprunner-ecr-role \
  --assume-role-policy-document file://trust-policy.json

aws iam attach-role-policy \
  --role-name warikan-apprunner-ecr-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

ECR_ROLE_ARN=$(aws iam get-role \
  --role-name warikan-apprunner-ecr-role \
  --query "Role.Arn" --output text)

rm trust-policy.json
```

### 10. AWS App Runner サービスの作成

```bash
cat > apprunner-config.json << CONFIG
{
  "ServiceName": "$APP_NAME",
  "SourceConfiguration": {
    "AuthenticationConfiguration": {
      "AccessRoleArn": "$ECR_ROLE_ARN"
    },
    "ImageRepository": {
      "ImageIdentifier": "$ECR_URI:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "MYSQL_HOST": "$RDS_ENDPOINT",
          "MYSQL_PORT": "3306",
          "MYSQL_USER": "$MYSQL_ADMIN_USER",
          "MYSQL_PASSWORD": "$MYSQL_ADMIN_PASSWORD",
          "MYSQL_DATABASE": "$MYSQL_DB_NAME",
          "MYSQL_SSL": "true",
          "SESSION_SECRET_KEY": "$(openssl rand -hex 32)"
        }
      }
    }
  },
  "InstanceConfiguration": {
    "Cpu": "0.25 vCPU",
    "Memory": "0.5 GB"
  },
  "NetworkConfiguration": {
    "EgressConfiguration": {
      "EgressType": "VPC",
      "VpcConnectorArn": "$CONNECTOR_ARN"
    }
  }
}
CONFIG

aws apprunner create-service --cli-input-json file://apprunner-config.json

rm apprunner-config.json
```

### 11. デプロイの確認

```bash
# サービスの URL を取得
aws apprunner describe-service \
  --service-arn $(aws apprunner list-services \
    --query "ServiceSummaryList[?ServiceName=='$APP_NAME'].ServiceArn" \
    --output text) \
  --query "Service.ServiceUrl" --output text
```

ブラウザで `https://<表示された URL>` にアクセスして動作確認してください。

---

## GitHub Actions による自動デプロイ (CI/CD)

### OIDC プロバイダーの設定（推奨）

長期的なアクセスキーの代わりに、GitHub Actions の OIDC 連携を使用します。

```bash
# GitHub OIDC プロバイダーを作成
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" \
  --client-id-list "sts.amazonaws.com"
```

### デプロイ用 IAM ロールの作成

```bash
GITHUB_ORG="hayashi1917"
GITHUB_REPO="warikan-app"

cat > github-trust-policy.json << POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main"
        }
      }
    }
  ]
}
POLICY

aws iam create-role \
  --role-name warikan-github-actions-role \
  --assume-role-policy-document file://github-trust-policy.json

# ECR と App Runner の権限を付与
aws iam attach-role-policy \
  --role-name warikan-github-actions-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

aws iam attach-role-policy \
  --role-name warikan-github-actions-role \
  --policy-arn arn:aws:iam::aws:policy/AWSAppRunnerFullAccess

rm github-trust-policy.json
```

### 必要な GitHub Secrets の設定

リポジトリの **Settings → Secrets and variables → Actions** で以下を設定します。

| シークレット名 | 値 |
|---|---|
| `AWS_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/warikan-github-actions-role` |
| `APP_RUNNER_ECR_ACCESS_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/warikan-apprunner-ecr-role` |

### ワークフローの動作

`.github/workflows/deploy-aws.yml` が設定済みです。`main` ブランチに push すると自動的に:

1. Docker イメージをビルド
2. ECR にプッシュ
3. App Runner にデプロイ

---

## コスト目安（月額）

| リソース | スペック | 目安コスト |
|---|---|---|
| App Runner | 0.25 vCPU / 0.5 GB | 約 $5〜15 (従量課金) |
| RDS for MySQL | db.t3.micro | 約 $15 |
| ECR | ストレージ | 約 $1 |
| **合計** | | **約 $21〜31/月（約 ¥3,200〜4,700）** |

> App Runner はリクエストがない時は自動的にスケールダウンするため、開発・テスト用途ではコストが低く抑えられます。
> RDS を無料枠（12ヶ月）で利用できる場合はさらに安くなります。

---

## Azure との比較

| 項目 | Azure | AWS |
|---|---|---|
| アプリ実行 | App Service (B1) | App Runner |
| DB | MySQL Flexible Server | RDS for MySQL |
| レジストリ | ACR | ECR |
| 月額目安 | 約 ¥5,200 | 約 ¥3,200〜4,700 |
| スケーリング | 手動（プラン変更） | 自動（リクエストベース） |
| セットアップ難易度 | 低い | やや高い（VPC 設定が必要） |
| SSL | 自動（無料） | 自動（無料） |

---

## トラブルシューティング

### App Runner のログを確認

```bash
SERVICE_ARN=$(aws apprunner list-services \
  --query "ServiceSummaryList[?ServiceName=='warikan-app'].ServiceArn" \
  --output text)

# CloudWatch Logs でログを確認
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/apprunner/warikan-app"
```

### RDS に接続できない場合

- VPC Connector が正しいサブネットとセキュリティグループを使用しているか確認
- セキュリティグループが 3306 ポートを VPC CIDR からのアクセスに開放しているか確認
- `MYSQL_SSL=true` が環境変数に設定されているか確認

### イメージの更新がデプロイされない場合

```bash
# App Runner を手動でデプロイ
aws apprunner start-deployment --service-arn $SERVICE_ARN
```
