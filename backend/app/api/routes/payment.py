from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


router = APIRouter(
    prefix="/payment",
    tags=["payment"],
)

@router.get("/")
def payment(request: Request):
    return templates.TemplateResponse("compute.html", {"request": request})

# todo @router.post("/")
