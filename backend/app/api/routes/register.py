from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

from app.schemas.schemas import GroupCreateRequest, LoginRequest
from app.services.register import authenticate_user, create_group_with_leader, create_user, get_group_by_name

templates = Jinja2Templates(directory="app/templates")

router = APIRouter(
    prefix="/register",
    tags=["register"],
)


@router.get("/start", name="register.start")
def start(request: Request):
    return templates.TemplateResponse("start.html", {"request": request})


@router.get("/me", name="register.me")
def me(request: Request):
    """セッションに保存されたログイン情報を返す。

    フロント側が localStorage ではなくこの API を使うことで、
    認証情報の管理をサーバーサイドセッションに一元化する。
    """
    group_id = request.session.get("group_id")
    group_name = request.session.get("group_name")
    user_name = request.session.get("user_name")
    if not group_id or not user_name:
        return JSONResponse(status_code=401, content={"message": "error", "detail": "Login required"})
    return {"group_id": group_id, "group_name": group_name, "user_name": user_name}


@router.post("/register_group")
def register_group_post(req: GroupCreateRequest, request: Request):
    """グループ作成 API。

    画面遷移は `redirect_url` として返すだけにし、フロント側が自由に遷移制御できるようにする。
    """
    try:
        result = create_group_with_leader(req.group_name, req.user_name, req.password)
        group_id = result["group_id"]
        group_name = result["group_name"]
        user_name = result["leader_user_name"]

        request.session["group_id"] = group_id
        request.session["group_name"] = group_name
        request.session["user_name"] = user_name

        return JSONResponse(
            content={
                "message": "ok",
                "group_id": group_id,
                "group_name": group_name,
                "user_name": user_name,
                "redirect_url": "/payment",
            }
        )
    except ValueError as exc:
        if str(exc) == "group_name already exists":
            return JSONResponse(status_code=409, content={"message": "error", "detail": str(exc)})
        return JSONResponse(status_code=400, content={"message": "error", "detail": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"message": "error", "detail": str(exc)})


@router.post("/join_group")
def join_group_post(req: GroupCreateRequest, request: Request):
    """既存グループへの参加 API。グループ名で検索し、新規ユーザーを作成する。"""
    try:
        group = get_group_by_name(req.group_name)
        if not group:
            return JSONResponse(status_code=404, content={"message": "error", "detail": "Group not found"})

        group_id = group["group_id"]
        result = create_user(group_id, req.user_name, req.password)
        user_name = result["user_name"]

        request.session["group_id"] = group_id
        request.session["group_name"] = req.group_name
        request.session["user_name"] = user_name

        return JSONResponse(
            content={
                "message": "ok",
                "group_id": group_id,
                "group_name": req.group_name,
                "user_name": user_name,
                "redirect_url": "/payment",
            }
        )
    except ValueError as exc:
        return JSONResponse(status_code=409, content={"message": "error", "detail": str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"message": "error", "detail": str(exc)})


@router.post("/login")
def login_post(req: LoginRequest, request: Request):
    """ログイン API。グループ名とユーザー名・パスワードで認証する。"""
    try:
        group = get_group_by_name(req.group_name)
        if not group:
            return JSONResponse(status_code=404, content={"message": "error", "detail": "Group not found"})
        group_id = group["group_id"]

        user = authenticate_user(group_id, req.user_name, req.password)
        if not user:
            return JSONResponse(status_code=401, content={"message": "error", "detail": "Invalid credentials"})

        request.session["group_id"] = group_id
        request.session["group_name"] = req.group_name
        request.session["user_name"] = user["user_name"]

        return JSONResponse(
            content={
                "message": "ok",
                "group_id": group_id,
                "group_name": req.group_name,
                "user_name": user["user_name"],
                "redirect_url": "/payment",
            }
        )

    except Exception as exc:
        return JSONResponse(status_code=500, content={"message": "error", "detail": str(exc)})
