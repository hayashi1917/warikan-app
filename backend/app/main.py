from dotenv import load_dotenv

load_dotenv(".env.local")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.api import api_router
import uvicorn

async def lifespan(app: FastAPI):
    yield

app = FastAPI(
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)  

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True, log_level="info")