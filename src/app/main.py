from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
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
    authenticate_payment_by_current_user
)
from .service import fetch_frankfurter_rates

app = FastAPI(title="Current Time App")

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web"
STATIC_VERSION = "20260303"

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


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
    leader_user_name: str = Field(min_length=1, max_length=50)
    leader_password: str = Field(min_length=8, max_length=128)


class UserCreateRequest(BaseModel):
    group_id: int = Field(gt=0)
    user_name: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=128)


@app.on_event("startup")
async def startup() -> None:
    ensure_schema()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, current_user: CurrentUser = Depends(get_current_user)):
    return templates.TemplateResponse(
        "html/index.html",
        {
            "request": request,
            "static_version": STATIC_VERSION,
            "current_user": current_user.model_dump(),
        },
    )


@app.get("/api/current-time")
async def current_time(current_user: CurrentUser = Depends(get_current_user)):
    now = datetime.now().astimezone()
    return {
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": now.strftime("%Z"),
        "utc_offset": now.strftime("%z"),
        "requested_by": current_user.model_dump(),
    }


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


@app.post("/api/groups")
async def create_group(payload: GroupCreateRequest):
    try:
        return {
            "created": True,
            "group": create_group_with_leader(
                group_name=payload.group_name,
                leader_user_name=payload.leader_user_name,
                leader_password=payload.leader_password,
            ),
        }
    except ValueError as exc:
        message = str(exc)
        code = 409 if "already exists" in message else 400
        raise HTTPException(status_code=code, detail=message)


@app.post("/api/users")
async def create_group_user(payload: UserCreateRequest):
    try:
        if not get_group(payload.group_id):
            raise HTTPException(status_code=404, detail="Group not found")
        if get_user(payload.group_id, payload.user_name):
            raise HTTPException(status_code=409, detail="User already exists in this group")
        create_user(payload.group_id, payload.user_name, payload.password)
        return {"created": True, "group_id": payload.group_id, "user_name": payload.user_name}
    except ValueError as exc:
        message = str(exc)
        code = 409 if "already belongs to group" in message else 400
        raise HTTPException(status_code=code, detail=message)


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


@app.post("/api/auth/token")
async def login_for_swagger(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        group_id_raw, user_name = form_data.username.split(":", 1)
        group_id = int(group_id_raw)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username must be formatted as '<group_id>:<user_name>'",
        ) from exc

    if group_id <= 0 or not user_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username must be formatted as '<group_id>:<user_name>'",
        )

    user = authenticate_user(group_id, user_name, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect group_id, user_name, or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(group_id=group_id, user_name=user_name)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/api/auth/me")
async def me(
    group_id: int = Query(..., gt=0, description="Target group ID"),
    current_user: CurrentUser = Depends(get_current_user),
):
    if group_id != current_user.group_id:
        raise HTTPException(status_code=403, detail="group_id does not match your login session")
    return current_user.model_dump()


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
