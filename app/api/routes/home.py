"""トップページ・About ページの描画ルート。"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(
    tags=["home"],
)


@router.get("/", name="home")
def home(request: Request):
    """トップページを表示する。"""
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/about", name="about")
def about(request: Request):
    """About ページを表示する。"""
    return templates.TemplateResponse("about.html", {"request": request})
