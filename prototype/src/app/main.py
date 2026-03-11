from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, model_validator

from .auth import CurrentUser, LoginRequest, create_access_token, get_current_user
from .db import (
    authenticate_user,
    create_group_with_leader,
    create_payment,
    create_user,
    ensure_schema,
    get_group,
    get_user,
    get_users,
    get_payments,
    authenticate_payment_by_current_user
)
from .service import fetch_frankfurter_rates
from .payment import create_matrix

app = FastAPI(title="Current Time App")

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web"
STATIC_VERSION = "20260303"

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

# ユーザ名と金額のモデル
class PaymentSplitInput(BaseModel):
    beneficiary_user_name: str = Field(min_length=1, max_length=50)
    amount: float = Field(gt=0)

# 支払い作成APIのリクエストモデル
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

# グループ名、リーダのユーザ名とPWを受け取るモデル
class GroupCreateRequest(BaseModel):
    group_name: str = Field(min_length=1, max_length=50)
    leader_user_name: str = Field(min_length=1, max_length=50)
    leader_password: str = Field(min_length=8, max_length=128)

# ユーザ登録のリクエストモデル
class UserCreateRequest(BaseModel):
    group_id: int = Field(gt=0)
    user_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)


@app.on_event("startup")
async def startup() -> None:
    ensure_schema()


# メイン画面の表示，htmlファイル割り当て
@app.get("/index.html", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "html/index.html",
        {
            "request": request,
            "static_version": STATIC_VERSION,
        },
    )


# ユーザ登録画面の表示，htmlファイル割り当て
@app.get("/join_group.html", response_class=HTMLResponse)
@app.get("/join-group", response_class=HTMLResponse)
async def join_group(request: Request):
    return templates.TemplateResponse(
        "html/join_group.html",
        {
            "request": request,
            "static_version": STATIC_VERSION,
        },
    )


# グループ登録画面の表示，htmlファイル割り当て
@app.get("/register_group.html", response_class=HTMLResponse)
@app.get("/register-group", response_class=HTMLResponse)
async def register_group(request: Request):
    return templates.TemplateResponse(
        "html/register_group.html",
        {
            "request": request,
            "static_version": STATIC_VERSION,
        },
    )


# ログイン画面の表示、htmlファイル割り当て
@app.get("/login.html", response_class=HTMLResponse)
@app.get("/login", response_class=HTMLResponse)
async def login_html(request: Request):
    return templates.TemplateResponse(
        "html/login.html",
        {
            "request": request,
            "static_version": STATIC_VERSION,
        },
    )


# 計算画面の表示、htmlファイル割り当て
@app.get("/compute.html", response_class=HTMLResponse)
@app.get("/compute", response_class=HTMLResponse)
async def compute(request: Request):
    return templates.TemplateResponse(
        "html/compute.html",
        {
            "request": request,
            "static_version": STATIC_VERSION,
        },
    )


# 現在時刻の取得API(テスト用)
@app.get("/api/current-time")
async def current_time():
    now = datetime.now().astimezone()
    return {
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": now.strftime("%Z"),
        "utc_offset": now.strftime("%z"),
    }


# 為替情報取得API
@app.get("/api/exchange-rate")
async def exchange_rate(
    base: str = Query("EUR", min_length=3, max_length=3, description="Base currency code"),
    symbols: str | None = Query(None, description="Comma-separated symbols. e.g. USD,JPY"),
    date: str = Query("latest", description="Date like 2026-03-04 or latest"),
):
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
        return fetch_frankfurter_rates(base=base.upper(), symbols=symbol_list, date=date)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch exchange rates: {exc}")


# ブラウザからのグループ参加(ユーザ登録)API
@app.post("/api/group", response_class=HTMLResponse)
async def join_group_from_form(
    request: Request,
    groupId: int = Form(..., gt=0),
    userId: str = Form(..., min_length=1, max_length=50),
    password: str = Form(..., min_length=8, max_length=128),
):
    try:
        if not get_group(groupId):
            return templates.TemplateResponse(
                "html/join_group.html",
                {"request": request, "static_version": STATIC_VERSION, "error": "Group not found"},
                status_code=404,
            )
        if get_user(groupId, userId):
            return templates.TemplateResponse(
                "html/join_group.html",
                {"request": request, "static_version": STATIC_VERSION, "error": "User already exists in this group"},
                status_code=409,
            )
        create_user(groupId, userId, password)
        token = create_access_token(group_id=groupId, user_name=userId)
        return templates.TemplateResponse(
            "html/join_group.html",
            {
                "request": request,
                "static_version": STATIC_VERSION,
                "success": True,
                "group_id": groupId,
                "user_id": userId,
                "access_token": token,
            },
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "html/join_group.html",
            {"request": request, "static_version": STATIC_VERSION, "error": str(exc)},
            status_code=400,
        )


# ブラウザからのグループ新規作成API
@app.post("/api/register-group", response_class=HTMLResponse)
async def register_group_from_form(
    request: Request,
    groupName: str = Form(..., min_length=1, max_length=50),
    leaderUserName: str = Form(..., min_length=1, max_length=50),
    leaderPassword: str = Form(..., min_length=8, max_length=128),
):
    try:
        created = create_group_with_leader(
            group_name=groupName,
            leader_user_name=leaderUserName,
            leader_password=leaderPassword,
        )
        token = create_access_token(group_id=created["group_id"], user_name=created["leader_user_name"])
        return templates.TemplateResponse(
            "html/register_group.html",
            {
                "request": request,
                "static_version": STATIC_VERSION,
                "success": True,
                "group_id": created["group_id"],
                "user_id": created["leader_user_name"],
                "access_token": token,
            },
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 409 if "already exists" in message else 400
        return templates.TemplateResponse(
            "html/register_group.html",
            {"request": request, "static_version": STATIC_VERSION, "error": message},
            status_code=status_code,
        )


# ブラウザからのログインAPI
@app.post("/api/login-form", response_class=HTMLResponse)
async def login_from_form(
    request: Request,
    groupId: int = Form(..., gt=0),
    userId: str = Form(..., min_length=1, max_length=50),
    password: str = Form(..., min_length=8, max_length=128),
):
    user = authenticate_user(groupId, userId, password)
    if not user:
        return templates.TemplateResponse(
            "html/login.html",
            {"request": request, "static_version": STATIC_VERSION, "error": "Incorrect group_id, user_name, or password"},
            status_code=401,
        )
    token = create_access_token(group_id=groupId, user_name=userId)
    return templates.TemplateResponse(
        "html/login.html",
        {
            "request": request,
            "static_version": STATIC_VERSION,
            "success": True,
            "group_id": groupId,
            "user_id": userId,
            "access_token": token,
        },
    )


# ログイン認証。bearerトークンを発行するAPI
@app.post("/api/auth/login")
async def login(payload: LoginRequest):
    user = authenticate_user(payload.group_id, payload.user_name, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect group_id, user_name, or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(group_id=payload.group_id, user_name=payload.user_name)
    return {"access_token": token, "token_type": "bearer"}


# 支払いの作成API
@app.post("/api/payment")
async def payment_create(payload: PaymentCreateRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        if payload.group_id != current_user.group_id:
            raise HTTPException(status_code=403, detail="group_id does not match your login session")
        payment_id = create_payment(
            group_id=current_user.group_id,
            login_user_name=current_user.user_name,
            title=payload.title,
            amount_total=payload.amount_total,
            currency_code=payload.currency_code.upper(),
            exchange_rate=payload.exchange_rate,
            splits=[item.model_dump() for item in payload.splits],
        )
        return {
            "saved": True,
            "requested_by": current_user.model_dump(),
            "payment_id": payment_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# 支払い一覧の取得API
@app.get("/api/payments")
async def payment_list(
    group_id: int = Query(..., alias="groupID", gt=0),
    current_user: CurrentUser = Depends(get_current_user),
):
    if group_id != current_user.group_id:
        raise HTTPException(status_code=403, detail="group_id does not match your login session")

    rows = get_payments(group_id)
    by_payment_id: dict[int, dict] = {}
    for row in rows:
        payment_id = int(row["payment_id"])
        if payment_id not in by_payment_id:
            by_payment_id[payment_id] = {
                "id": payment_id,
                "payer": row["paid_by_user_name"],
                "total": float(row["amount_total"]),
                "currencyCode": row["currency_code"],
                "title": row["title"],
                "details": [],
                "approvedBy": [],
            }
        by_payment_id[payment_id]["details"].append(
            {
                "name": row["beneficiary_user_name"],
                "amount": float(row["amount"]),
            }
        )
        if row["approved"]:
            by_payment_id[payment_id]["approvedBy"].append(row["beneficiary_user_name"])

    return list(by_payment_id.values())


# 支払い承認API
@app.post("/api/payment/{payment_id}/approve")
async def payment_approve(
    payment_id: int,
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        if payment_id <= 0:
            raise HTTPException(status_code=400, detail="payment_id must be greater than 0")
        success = authenticate_payment_by_current_user(
            group_id=current_user.group_id,
            payment_id=payment_id,
            current_user_name=current_user.user_name,
        )
        if not success:
            raise HTTPException(status_code=404, detail="No approvable payment split found for current user")
        return {
            "approved": True,
            "payment_id": payment_id,
            "approved_by": current_user.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# 所属グループ内のユーザ一覧取得API
@app.get("/api/get-users")
async def get_group_users(group_id: int, current_user: CurrentUser = Depends(get_current_user)):
    # グループIDがログインユーザのものと違う場合はエラー
    if group_id != current_user.group_id:
        raise HTTPException(status_code=403, detail="group_id does not match your login session")
    rows = get_users(group_id)
    return {"users": [row["user_name"] for row in rows]}


# 支払いの計算API
@app.get("/api/create-matrix")
async def create_matrix_endpoint(
    group_id: int = Query(..., alias="groupID", gt=0),
    current_user: CurrentUser = Depends(get_current_user),
):
    if group_id != current_user.group_id:
        raise HTTPException(status_code=403, detail="group_id does not match your login session")
    return {"instructions": create_matrix(group_id)}
