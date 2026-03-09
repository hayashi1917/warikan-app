from pydantic import BaseModel, Field, model_validator

class PaymentSplitInput(BaseModel):
    beneficiary_user_name: str = Field(min_length=1, max_length=50)
    amount: float = Field(gt=0)


class PaymentCreateRequest(BaseModel):
    group_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=100)
    amount_total: float = Field(gt=0)
    currency_code: str = Field(default="EUR", min_length=3, max_length=3)
    exchange_rate: float = Field(default=1.0, gt=0)
    splits: list[PaymentSplitInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_total(self):
        total = round(sum(item.amount for item in self.splits), 2)
        if round(self.amount_total, 2) != total:
            raise ValueError("amount_total must equal the sum of split amounts")
        return self

class GroupCreateRequest(BaseModel):
    group_name: str = Field(min_length=1, max_length=50)
    user_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)

class UserCreateRequest(BaseModel):
    group_name: str = Field(min_length=1, max_length=50)
    user_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)

class RegisterRequest(BaseModel):
    group_name: str
    user_name: str
    password: str


class LoginRequest(BaseModel):
    group_name: str
    user_name: str
    password: str


class CurrentUser(BaseModel):
    group_name: str
    user_name: str
