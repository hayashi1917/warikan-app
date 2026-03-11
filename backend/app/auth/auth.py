"""パスワードハッシュ化・認証ユーティリティ。"""

import hashlib
import hmac

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """パスワードを bcrypt でハッシュ化する。"""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """パスワードをハッシュと照合する。bcrypt と旧 SHA256 の両方に対応。"""
    if password_hash.startswith("$2"):
        return pwd_context.verify(password, password_hash)
    # レガシー SHA256 ハッシュとの互換性を維持
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(password_hash, legacy_hash)
