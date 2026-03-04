from fastapi import APIRouter
from .routes.home import router as home_router
from .routes.payment import router as payment_router
from .routes.register import router as register_router

api_router = APIRouter()

api_router.include_router(home_router)
api_router.include_router(payment_router)
api_router.include_router(register_router)


# @app.on_event("startup")
# async def startup() -> None:
#     ensure_schema()


# # @app.get("/", response_class=HTMLResponse)
# # async def index(request: Request):
# #     return templates.TemplateResponse(
# #         "html/index.html",
# #         {
# #             "request": request,
# #             "static_version": STATIC_VERSION,
# #         },
# #     )


# @app.get("/")
# async def home():
#     return templates.TemplateResponse("index.html", {"request": request})

# @app.get("/api/current-time")
# async def current_time():
#     now = datetime.now().astimezone()
#     return {
#         "iso": now.isoformat(),
#         "date": now.strftime("%Y-%m-%d"),
#         "time": now.strftime("%H:%M:%S"),
#         "timezone": now.strftime("%Z"),
#         "utc_offset": now.strftime("%z"),
#     }


# @app.get("/api/exchange-rate")
# async def exchange_rate(
#     base: str = Query("EUR", min_length=3, max_length=3, description="Base currency code"),
#     symbols: str | None = Query(None, description="Comma-separated symbols. e.g. USD,JPY"),
#     date: str = Query("latest", description="Date like 2026-03-04 or latest"),
# ):
#     try:
#         symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
#         return fetch_frankfurter_rates(base=base.upper(), symbols=symbol_list, date=date)
#     except Exception as exc:
#         raise HTTPException(status_code=502, detail=f"Failed to fetch exchange rates: {exc}")


# @app.post("/api/groups")
# async def create_group(payload: GroupCreateRequest):
#     try:
#         return {
#             "created": True,
#             "group": create_group_with_leader(
#                 group_name=payload.group_name,
#                 leader_user_name=payload.leader_user_name,
#                 leader_password=payload.leader_password,
#             ),
#         }
#     except ValueError as exc:
#         message = str(exc)
#         code = 409 if "already exists" in message else 400
#         raise HTTPException(status_code=code, detail=message)


# @app.post("/api/users")
# async def create_group_user(payload: UserCreateRequest):
#     try:
#         if not get_group(payload.group_id):
#             raise HTTPException(status_code=404, detail="Group not found")
#         if get_user(payload.group_id, payload.user_name):
#             raise HTTPException(status_code=409, detail="User already exists in this group")
#         create_user(payload.group_id, payload.user_name, payload.password)
#         return {"created": True, "group_id": payload.group_id, "user_name": payload.user_name}
#     except ValueError as exc:
#         message = str(exc)
#         code = 409 if "already belongs to group" in message else 400
#         raise HTTPException(status_code=code, detail=message)


# @app.post("/api/auth/login")
# async def login(payload: LoginRequest):
#     user = authenticate_user(payload.group_id, payload.user_name, payload.password)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect group_id, user_name, or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     token = create_access_token(group_id=payload.group_id, user_name=payload.user_name)
#     return {"access_token": token, "token_type": "bearer"}


# @app.post("/api/auth/token")
# async def login_for_swagger(form_data: OAuth2PasswordRequestForm = Depends()):
#     try:
#         group_id_raw, user_name = form_data.username.split(":", 1)
#         group_id = int(group_id_raw)
#     except Exception as exc:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="username must be formatted as '<group_id>:<user_name>'",
#         ) from exc

#     if group_id <= 0 or not user_name:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="username must be formatted as '<group_id>:<user_name>'",
#         )

#     user = authenticate_user(group_id, user_name, form_data.password)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect group_id, user_name, or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

#     token = create_access_token(group_id=group_id, user_name=user_name)
#     return {"access_token": token, "token_type": "bearer"}


# @app.get("/api/auth/me")
# async def me(
#     group_id: int = Query(..., gt=0, description="Target group ID"),
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     if group_id != current_user.group_id:
#         raise HTTPException(status_code=403, detail="group_id does not match your login session")
#     return current_user.model_dump()


# @app.post("/api/payment")
# async def payment_create(payload: PaymentCreateRequest, current_user: CurrentUser = Depends(get_current_user)):
#     try:
#         if payload.group_id != current_user.group_id:
#             raise HTTPException(status_code=403, detail="group_id does not match your login session")
#         payment_id = create_payment(
#             group_id=current_user.group_id,
#             login_user_name=current_user.user_name,
#             title=payload.title,
#             amount_total=payload.amount_total,
#             currency_code=payload.currency_code.upper(),
#             exchange_rate=payload.exchange_rate,
#             splits=[item.model_dump() for item in payload.splits],
#         )
#         return {
#             "saved": True,
#             "requested_by": current_user.model_dump(),
#             "payment_id": payment_id,
#         }
#     except ValueError as exc:
#         raise HTTPException(status_code=400, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))

# @app.post("/api/payment/{payment_id}/approve")
# async def payment_approve(
#     payment_id: int,
#     current_user: CurrentUser = Depends(get_current_user),
# ):
#     try:
#         if payment_id <= 0:
#             raise HTTPException(status_code=400, detail="payment_id must be greater than 0")
#         success = authenticate_payment_by_current_user(
#             group_id=current_user.group_id,
#             payment_id=payment_id,
#             current_user_name=current_user.user_name,
#         )
#         if not success:
#             raise HTTPException(status_code=404, detail="No approvable payment split found for current user")
#         return {
#             "approved": True,
#             "payment_id": payment_id,
#             "approved_by": current_user.model_dump(),
#         }
#     except HTTPException:
#         raise
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))
