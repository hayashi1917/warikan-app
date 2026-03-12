"""リクエスト/レスポンスのバリデーションスキーマ定義。"""

from decimal import Decimal

from pydantic import AliasChoices, BaseModel, Field, model_validator


class PaymentSplitInput(BaseModel):
    """支払い明細の1行分（受益者と金額）。"""
    beneficiary_user_name: str = Field(
        validation_alias=AliasChoices("beneficiary_user_name", "beneficiaryUserName"),
        min_length=1,
        max_length=50,
    )
    amount: float = Field(gt=0)


class PaymentCreateRequest(BaseModel):
    """支払い作成リクエスト。

    exchange_rate はサーバー側で為替 API から取得するため、クライアントからは受け取らない。
    """
    group_id: int = Field(validation_alias=AliasChoices("group_id", "groupID"), gt=0)
    title: str = Field(min_length=1, max_length=100)
    amount_total: float = Field(validation_alias=AliasChoices("amount_total", "amountTotal"), gt=0)
    currency_code: str = Field(
        default="JPY",
        validation_alias=AliasChoices("currency_code", "currencyCode"),
        min_length=3,
        max_length=3,
    )
    splits: list[PaymentSplitInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_total(self):
        # NOTE: クライアント側の浮動小数誤差（0.1 + 0.2 など）を許容する。
        total = sum(Decimal(str(item.amount)) for item in self.splits)
        requested_total = Decimal(str(self.amount_total))
        if abs(total - requested_total) > Decimal("0.01"):
            raise ValueError("amount_total must equal the sum of split amounts")
        return self


class GroupCreateRequest(BaseModel):
    """グループ作成・グループ参加の共通リクエスト。"""
    group_name: str = Field(min_length=1, max_length=50)
    user_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """ログインリクエスト。バリデーション制約は緩めに設定し、認証ロジックに委ねる。"""
    group_name: str
    user_name: str
    password: str


class CurrentUser(BaseModel):
    """現在ログイン中のユーザー情報。"""
    group_name: str
    user_name: str
