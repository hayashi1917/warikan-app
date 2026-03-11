"""API ルーター集約モジュール。

各機能ルーターをここで束ねることで、エントリポイント(main.py)から
依存関係を単純化し、バックエンドのディレクトリ構成を理解しやすくする。
"""

from fastapi import APIRouter

from .routes.home import router as home_router
from .routes.payment import router as payment_router
from .routes.register import router as register_router

api_router = APIRouter()
api_router.include_router(home_router)
api_router.include_router(payment_router)
api_router.include_router(register_router)
