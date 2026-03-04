

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