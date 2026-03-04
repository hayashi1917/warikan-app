import hashlib
import hmac
import os
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Sequence

import pymysql
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _mysql_config() -> Dict[str, Any]:
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "canon_milc_info"),
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": pymysql.cursors.DictCursor,
    }


@contextmanager
def mysql_connection() -> Generator[pymysql.connections.Connection, None, None]:
    conn = pymysql.connect(**_mysql_config())
    try:
        yield conn
    finally:
        conn.close()


def ensure_schema() -> None:
    queries = [
        """
        CREATE TABLE IF NOT EXISTS `groups` (
          group_id INT AUTO_INCREMENT PRIMARY KEY,
          group_name VARCHAR(50) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS `users` (
          group_id INT NOT NULL,
          user_name VARCHAR(50) NOT NULL,
          password_hash VARCHAR(255) NOT NULL,
          PRIMARY KEY (group_id, user_name),
          CONSTRAINT fk_users_group
            FOREIGN KEY (group_id)
            REFERENCES `groups`(group_id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS `payments` (
          payment_id INT AUTO_INCREMENT PRIMARY KEY,
          group_id INT NOT NULL,
          paid_by_user_name VARCHAR(50) NOT NULL,
          title VARCHAR(100) NOT NULL,
          amount_total DECIMAL(12,2) NOT NULL,
          currency_code CHAR(3) NOT NULL,
          exchange_rate DECIMAL(10,4) NOT NULL,
          payment_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_payments_group
            FOREIGN KEY (group_id)
            REFERENCES `groups`(group_id)
            ON DELETE CASCADE,
          CONSTRAINT fk_payments_paid_by
            FOREIGN KEY (group_id, paid_by_user_name)
            REFERENCES `users`(group_id, user_name)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS `payment_splits` (
          payment_id INT NOT NULL,
          group_id INT NOT NULL,
          beneficiary_user_name VARCHAR(50) NOT NULL,
          amount DECIMAL(12,2) NOT NULL,
          approved BOOLEAN NOT NULL DEFAULT FALSE,
          PRIMARY KEY (payment_id, beneficiary_user_name),
          CONSTRAINT fk_splits_payment
            FOREIGN KEY (payment_id)
            REFERENCES `payments`(payment_id)
            ON DELETE CASCADE,
          CONSTRAINT fk_splits_beneficiary
            FOREIGN KEY (group_id, beneficiary_user_name)
            REFERENCES `users`(group_id, user_name)
            ON DELETE CASCADE
            ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
    ]
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            for q in queries:
                cur.execute(q)
        conn.commit()

# パスワードハッシュ関数
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# パスワード認証関数
def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$2"):
        return pwd_context.verify(password, password_hash)
    legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(password_hash, legacy_hash)

# グループ作成
def create_group(cur: pymysql.cursors.Cursor, group_name: str) -> int:
    cur.execute("INSERT INTO `groups` (group_name) VALUES (%s)", (group_name,))
    return int(cur.lastrowid)

# グループidからグループ名を取得
def get_group(group_id: int) -> Optional[Dict[str, Any]]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT group_id, group_name
                FROM `groups`
                WHERE group_id = %s
                LIMIT 1
                """,
                (group_id,),
            )
            row = cur.fetchone()
    return row

# グループ新規作成とリーダのユーザ作成
def create_group_with_leader(group_name: str, leader_user_name: str, leader_password: str) -> Dict[str, Any]:
    ensure_schema()

    with mysql_connection() as conn:
        with conn.cursor() as cur:
            group_id = create_group(cur, group_name)
            cur.execute(
                "INSERT INTO `users` (group_id, user_name, password_hash) VALUES (%s, %s, %s)",
                (group_id, leader_user_name, hash_password(leader_password)),
            )
        conn.commit()

    return {"group_id": group_id, "group_name": group_name, "leader_user_name": leader_user_name}

# グループに所属するユーザ作成
def create_user(group_id: int, user_name: str, password: str) -> None:
    # 名前がすでに存在していればエラー
    if get_user(group_id, user_name):
        raise ValueError("user_name already exists in this group")
    password_hash = hash_password(password)
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO `users` (group_id, user_name, password_hash) VALUES (%s, %s, %s)",
                (group_id, user_name, password_hash),
            )
        conn.commit()

# グループに所属する全ユーザを取得
def get_users(group_id: int) -> Optional[List[Dict[str, Any]]]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT group_id, user_name
                FROM `users`
                WHERE group_id = %s
                """,
                (group_id),
            )
            row = cur.fetchall()
    return row

# グループに所属するユーザ情報をユーザ名から取得
def get_user(group_id: int, user_name: str) -> Optional[Dict[str, Any]]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT group_id, user_name, password_hash
                FROM `users`
                WHERE group_id = %s AND user_name = %s
                LIMIT 1
                """,
                (group_id, user_name),
            )
            row = cur.fetchone()
    return row

# ユーザ認証
def authenticate_user(group_id: int, user_name: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user(group_id, user_name)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user

# 支払いの作成
def create_payment(
    group_id: int,
    login_user_name: str,
    title: str,
    amount_total: float,
    currency_code: str,
    exchange_rate: float,
    splits: List[Dict[str, Any]],
) -> int:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            # 概要の登録
            cur.execute(
                """
                INSERT INTO `payments` (group_id, paid_by_user_name, title, amount_total, currency_code, exchange_rate)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (group_id, login_user_name, title, amount_total, currency_code, exchange_rate),
            )
            payment_id = int(cur.lastrowid)
            # 詳細の登録
            for split in splits:
                cur.execute(
                    """
                    INSERT INTO `payment_splits` (payment_id, group_id, beneficiary_user_name, amount)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (payment_id, group_id, split["beneficiary_user_name"], split["amount"]),
                )
        conn.commit()
    return payment_id

# 支払い承認
def authenticate_payment_by_current_user(group_id: int, payment_id: int, current_user_name: str) -> bool:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE `payment_splits`
                SET approved = TRUE
                WHERE payment_id = %s AND group_id = %s AND beneficiary_user_name = %s
                """,
                (payment_id, group_id, current_user_name),
            )
            updated_rows = cur.rowcount
            conn.commit()
    return updated_rows > 0
