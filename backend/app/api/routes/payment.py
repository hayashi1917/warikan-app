from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.services.services import (
    authenticate_payment_by_current_user,
    create_payment,
    list_group_payments,
    delete_payment,
    resolve_jpy_exchange_rate,
)
from app.services.payments import calculate_group_settlements
from app.services.register import get_users
from app.schemas.schemas import PaymentCreateRequest

templates = Jinja2Templates(directory="app/templates")


router = APIRouter(
    prefix="/payment",
    tags=["payment"],
)

@router.get("/", name="payment")
def payment(request: Request):
    if not request.session.get("group_name") or not request.session.get("user_name"):
        return RedirectResponse(url="/register/start", status_code=303)
    group_id = request.session.get("group_id")
    users = get_users(group_id) if group_id else []
    member_names = [user["user_name"] for user in users]
    return templates.TemplateResponse("compute.html", {"request": request, "member_names": member_names})


@router.post("/create", name="create_payment")
def create_payment_post(request: Request, req: PaymentCreateRequest):
    try:
        login_user_name = request.session.get("user_name", "")
        exchange_rate = resolve_jpy_exchange_rate(req.currency_code)
        success, result = create_payment(
            group_id=req.group_id,
            login_user_name=login_user_name,
            title=req.title,
            amount_total=req.amount_total,
            currency_code=req.currency_code,
            exchange_rate=exchange_rate,
            splits=[s.model_dump() for s in req.splits],
        )
        if success:
            return JSONResponse(content={"status": "success", "payment_id": result})
        else:
            return JSONResponse(status_code=500, content={"status": "error", "detail": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})



@router.delete("/{payment_id}", name="delete_payment")
def delete_payment_by_id(payment_id: int, request: Request):
    try:
        group_id = request.session.get("group_id")
        user_name = request.session.get("user_name")
        if not group_id or not user_name:
            return JSONResponse(status_code=401, content={"status": "error", "detail": "ログイン情報がありません"})

        success, result = delete_payment(
            group_id=int(group_id),
            payment_id=payment_id,
            current_user_name=user_name,
        )
        if success:
            return JSONResponse(content={"status": "success"})
        return JSONResponse(status_code=403, content={"status": "error", "detail": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@router.post("/authenticate", name="authenticate_payment")
def authenticate_payment(request: Request, group_id: int, payment_id: int):
    current_user_name = request.session.get("user_name", "")
    if not current_user_name:
        raise HTTPException(status_code=401, detail="ログインが必要です")

    approved = authenticate_payment_by_current_user(
        group_id=group_id,
        payment_id=payment_id,
        current_user_name=current_user_name,
    )
    if not approved:
        raise HTTPException(status_code=404, detail="承認対象が見つかりません")
    return {"status": "success", "payment_id": payment_id, "approved_by": current_user_name}


@router.get("/list", name="list_payments")
def list_payments(group_id: int = Query(..., gt=0)):
    try:
        payments = list_group_payments(group_id)
        unapproved_payments = [p for p in payments if not p["is_approved"]]
        approved_payments = [p for p in payments if p["is_approved"]]
        return {
            "status": "success",
            "all": payments,
            "unapproved": unapproved_payments,
            "approved": approved_payments,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


@router.get("/settlements", name="settlements")
def settlements(group_id: int = Query(..., gt=0)):
    try:
        return {"status": "success", "result": calculate_group_settlements(group_id)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})
