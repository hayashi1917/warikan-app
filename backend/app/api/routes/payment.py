from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.services.services import create_payment
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
    return templates.TemplateResponse("compute.html", {"request": request})


@router.post("/create", name="create_payment")
def create_payment_post(request: Request, req: PaymentCreateRequest):
    try:
        login_user_name = request.session.get("user_name", "")
        success, result = create_payment(
            group_id=req.group_id,
            login_user_name=login_user_name,
            title=req.title,
            amount_total=req.amount_total,
            currency_code=req.currency_code,
            exchange_rate=req.exchange_rate,
            splits=[s.model_dump() for s in req.splits],
        )
        if success:
            return JSONResponse(content={"status": "success", "payment_id": result})
        else:
            return JSONResponse(status_code=500, content={"status": "error", "detail": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

@router.post("/authenticate", name="authenticate_payment")
def authenticate_payment(request: Request):
    pass
