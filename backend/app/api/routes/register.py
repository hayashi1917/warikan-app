from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from ....schemas import GroupCreateRequest

templates = Jinja2Templates(directory="app/templates")


router = APIRouter(
    prefix="/register",
    tags=["register"],
)

@router.get("/register_group", name="register.register_group")
def register_group(request: Request):
    return templates.TemplateResponse("register_group.html", {"request": request})

@router.post("/register_group")
def register_group_post(request: Request, payload: GroupCreateRequest):
    return templates.TemplateResponse("register_group.html", {"request": request})

@router.get("/join_group", name="register.join_group")
def join_group(request: Request):
    return templates.TemplateResponse("join_group.html", {"request": request})

# todo @router.post("/join_group")

@router.get("/login", name="register.login")
def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# todo @router.post("/login")

