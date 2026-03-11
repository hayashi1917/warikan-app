import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .db import get_user

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


class RegisterRequest(BaseModel):
    group_name: str
    user_name: str
    password: str


class LoginRequest(BaseModel):
    group_id: int
    user_name: str
    password: str


class CurrentUser(BaseModel):
    group_id: int
    user_name: str


def create_access_token(group_id: int, user_name: str, expires_minutes: Optional[int] = None) -> str:
    exp_minutes = expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=exp_minutes)
    payload = {
        "sub": user_name,
        "group_id": group_id,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_name = payload.get("sub")
        group_id = payload.get("group_id")
        if not user_name or group_id is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    user = get_user(int(group_id), str(user_name))
    if not user:
        raise credentials_exception

    return CurrentUser(group_id=int(group_id), user_name=str(user_name))
