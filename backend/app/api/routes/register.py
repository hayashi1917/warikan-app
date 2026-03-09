from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.schemas.schemas import GroupCreateRequest, LoginRequest
from app.services.register import create_group_with_leader, create_user, authenticate_user, get_group_by_name

templates = Jinja2Templates(directory="app/templates")


router = APIRouter(
    prefix="/register",
    tags=["register"],
)

@router.get("/start", name="register.start")
def start(request: Request):
    return templates.TemplateResponse("start.html", {"request": request})

@router.post("/register_group")
def register_group_post(req: GroupCreateRequest, request: Request):
    try:
        # グループ登録&作成者ユーザー登録
        result = create_group_with_leader(req.group_name, req.user_name, req.password)
        group_id = result["group_id"]
        group_name = result["group_name"]
        user_name = result["leader_user_name"]
        print(f"group: {group_id}, group_name: {group_name}, user_name: {user_name}")

        # ログイン状態を作成
        request.session["group_id"] = group_id
        request.session["group_name"] = group_name
        request.session["user_name"] = user_name

        return JSONResponse(content={
            "message": "ok",
            "group_id": group_id,
            "group_name": group_name,
            "user_name": user_name,
            "redirect_url": "/payment"
        })
    except ValueError as e:
        if str(e) == "group_name already exists":
            return JSONResponse(status_code=409, content={"message": "error", "detail": str(e)})
        return JSONResponse(status_code=400, content={"message": "error", "detail": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": "error", "detail": str(e)})

@router.post("/join_group")
def join_group_post(req: GroupCreateRequest, request: Request):
    try:
        # グループ名からグループIDを取得
        group = get_group_by_name(req.group_name)
        if not group:
            return JSONResponse(status_code=404, content={"message": "error", "detail": "Group not found"})
        group_id = group["group_id"]

        # ユーザー登録
        result = create_user(group_id, req.user_name, req.password)
        user_name = result["user_name"]
        print(f"group: {group_id}, group_name: {req.group_name}, user_name: {user_name}")

        # ログイン状態を作成
        request.session["group_id"] = group_id
        request.session["group_name"] = req.group_name
        request.session["user_name"] = user_name

        return JSONResponse(content={
            "message": "ok",
            "group_id": group_id,
            "group_name": req.group_name,
            "user_name": user_name,
            "redirect_url": "/payment"
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": "error", "detail": str(e)})

# todo 
@router.post("/login")
def login_post(req: LoginRequest, request: Request):
    try:
        # グループ名からグループIDを取得
        group = get_group_by_name(req.group_name)
        if not group:
            return JSONResponse(status_code=404, content={"message": "error", "detail": "Group not found"})
        group_id = group["group_id"]

        # ログイン認証
        user = authenticate_user(group_id, req.user_name, req.password)
        if not user:
            return JSONResponse(content={
                "message": "error",
                "detail": "Invalid credentials"
            })
        print(f"group: {user['group_id']}, group_name: {req.group_name}, user_name: {user['user_name']}")

        # ログイン状態を作成
        request.session["group_id"] = group_id
        request.session["group_name"] = req.group_name
        request.session["user_name"] = user["user_name"]

        return JSONResponse(content={
            "message": "ok",
            "group_id": group_id,
            "group_name": req.group_name,
            "user_name": user["user_name"],
            "redirect_url": "/payment"
        })

    except Exception as e:
        return JSONResponse(status_code=500, content={"message": "error", "detail": str(e)})

