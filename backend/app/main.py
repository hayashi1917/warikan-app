import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.db.db import ensure_schema
from app.api.api import api_router

# ローカル開発用の環境変数を先に読み込む。
load_dotenv(".env.local")


async def lifespan(_: FastAPI):
    """アプリ起動時に最低限必要な DB スキーマを保証する。"""
    ensure_schema()
    yield


app = FastAPI(lifespan=lifespan)

# フロントエンド分離開発を優先し、API の利用元を限定しない構成にしている。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#   
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "change-me-to-a-random-secret"),
)

app.include_router(api_router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True, log_level="info")
