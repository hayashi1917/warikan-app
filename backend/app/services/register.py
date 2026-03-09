"""ユーザー/グループ登録に関するサービス層。

フロントエンドの実装詳細（テンプレートや画面遷移）と独立して利用できるように、
このモジュールでは DB アクセスと認証ロジックのみを担当する。
"""

from typing import Any, Dict, List, Optional

import pymysql.cursors

from app.auth.auth import hash_password, verify_password
from app.db.db import mysql_connection


# グループ作成
# ルートハンドラ側に SQL 詳細を漏らさないため、内部関数として切り出している。
def _create_group(cur: pymysql.cursors.Cursor, group_name: str) -> int:
    cur.execute("INSERT INTO `groups` (group_name) VALUES (%s)", (group_name,))
    return int(cur.lastrowid)


# グループIDからグループ情報を取得
# 返却フォーマットを固定することで、呼び出し元が DB カラム変更の影響を受けにくくなる。
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


# グループ名からグループ情報を取得
def get_group_by_name(group_name: str) -> Optional[Dict[str, Any]]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT group_id, group_name
                FROM `groups`
                WHERE group_name = %s
                LIMIT 1
                """,
                (group_name,),
            )
            row = cur.fetchone()
    return row


# グループ新規作成とリーダーユーザー作成
# 一連の登録は同一トランザクションにまとめ、途中失敗時の不整合を防止する。
def create_group_with_leader(group_name: str, leader_user_name: str, leader_password: str) -> Dict[str, Any]:
    if get_group_by_name(group_name):
        raise ValueError("group_name already exists")

    with mysql_connection() as conn:
        with conn.cursor() as cur:
            group_id = _create_group(cur, group_name)
            cur.execute(
                "INSERT INTO `users` (group_id, user_name, password_hash) VALUES (%s, %s, %s)",
                (group_id, leader_user_name, hash_password(leader_password)),
            )
        conn.commit()

    return {"group_id": group_id, "group_name": group_name, "leader_user_name": leader_user_name}


# グループ所属ユーザーの作成
# 同一グループ内でのユーザー名重複を防止し、API から利用しやすい辞書形式で返却する。
def create_user(group_id: int, user_name: str, password: str) -> Dict[str, Any]:
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
    return {"group_id": group_id, "user_name": user_name}


# グループに所属する全ユーザーを取得
# SQL パラメータは必ずタプルにし、ドライバ差異によるバグを防ぐ。
def get_users(group_id: int) -> List[Dict[str, Any]]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT group_id, user_name
                FROM `users`
                WHERE group_id = %s
                ORDER BY user_name ASC
                """,
                (group_id,),
            )
            rows = cur.fetchall()
    return rows


# グループ所属ユーザーをユーザー名で取得
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


# ユーザー認証
# ハッシュ化方式の詳細は auth モジュールに委譲し、サービス層では認証可否のみを返す。
def authenticate_user(group_id: int, user_name: str, password: str) -> Optional[Dict[str, Any]]:
    user = get_user(group_id, user_name)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user
