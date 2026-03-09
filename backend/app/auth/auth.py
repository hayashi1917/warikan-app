import hashlib
import hmac
import os

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# パスワードハッシュ関数
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# パスワード認証関数
def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$2"):
        return pwd_context.verify(password, password_hash)
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(password_hash, legacy_hash)
