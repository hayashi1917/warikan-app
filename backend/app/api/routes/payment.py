from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.schemas.schemas import PaymentCreateRequest
from app.services.settlement import calculate_group_settlements
from app.services.register import get_users
from app.services.payment_service import (
    authenticate_payment_by_current_user,
    create_payment,
    delete_payment,
    list_group_payments,
    resolve_jpy_exchange_rate,
)

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(
    prefix="/payment",
    tags=["payment"],
)


def _require_login(request: Request) -> tuple[int, str]:
    """セッションからログイン情報を取得し、未ログインなら 401 を送出する。"""
    group_id = request.session.get("group_id")
    user_name = request.session.get("user_name")
    if not group_id or not user_name:
        raise HTTPException(status_code=401, detail="ログイン情報がありません")
    return int(group_id), str(user_name)


# 描画ルート
# API と分離しているため、フロント実装が SPA 化されてもこの処理は最小修正で差し替え可能。
@router.get("/", name="payment")
def payment(request: Request):
    if not request.session.get("group_name") or not request.session.get("user_name"):
        return RedirectResponse(url="/register/start", status_code=303)

    return templates.TemplateResponse("compute.html", {"request": request})


@router.get("/members", name="payment_members")
def payment_members(request: Request):
    """グループメンバー一覧 API。テンプレート変数ではなく API 経由で返す。"""
    group_id, _ = _require_login(request)
    users = get_users(group_id)
    return {"members": [user["user_name"] for user in users]}


# API ルート
@router.post("/create", name="create_payment")
def create_payment_post(request: Request, req: PaymentCreateRequest):
    """支払い登録 API。ログインユーザーのグループに紐づけて支払いを作成する。"""
    try:
        group_id, login_user_name = _require_login(request)

        exchange_rate = resolve_jpy_exchange_rate(req.currency_code)
        success, result = create_payment(
            group_id=group_id,
            login_user_name=login_user_name,
            title=req.title,
            amount_total=req.amount_total,
            currency_code=req.currency_code,
            exchange_rate=exchange_rate,
            splits=[s.model_dump() for s in req.splits],
        )
        if success:
            return JSONResponse(content={"status": "success", "payment_id": result})
        return JSONResponse(status_code=400, content={"status": "error", "detail": result})
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


@router.delete("/{payment_id}", name="delete_payment")
def delete_payment_by_id(payment_id: int, request: Request):
    """支払い削除 API。作成者本人のみ削除可能。"""
    try:
        group_id, user_name = _require_login(request)

        success, result = delete_payment(
            group_id=group_id,
            payment_id=payment_id,
            current_user_name=user_name,
        )
        if success:
            return JSONResponse(content={"status": "success"})
        return JSONResponse(status_code=403, content={"status": "error", "detail": result})
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


@router.post("/authenticate", name="authenticate_payment")
def authenticate_payment(request: Request, payment_id: int):
    """支払い承認 API。セッションのグループIDを使い、他グループの承認を防止する。"""
    group_id, current_user_name = _require_login(request)

    approved = authenticate_payment_by_current_user(
        group_id=group_id,
        payment_id=payment_id,
        current_user_name=current_user_name,
    )
    if not approved:
        raise HTTPException(status_code=404, detail="承認対象が見つかりません")
    return {"status": "success", "payment_id": payment_id, "approved_by": current_user_name}


@router.get("/list", name="list_payments")
def list_payments(request: Request):
    """グループ支払い一覧 API。セッションのグループIDを使い、他グループの閲覧を防止する。"""
    try:
        group_id, _ = _require_login(request)
        payments = list_group_payments(group_id)
        return {
            "status": "success",
            "all": payments,
            "unapproved": [p for p in payments if not p["is_approved"]],
            "approved": [p for p in payments if p["is_approved"]],
        }
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})


@router.get("/settlements", name="settlements")
def settlements(request: Request):
    """最小フロー精算 API。セッションのグループIDを使い、他グループの閲覧を防止する。"""
    try:
        group_id, _ = _require_login(request)
        return {"status": "success", "result": calculate_group_settlements(group_id)}
    except HTTPException:
        raise
    except Exception as exc:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(exc)})
