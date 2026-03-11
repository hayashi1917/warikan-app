"""支払い関連のユースケースを提供するサービス層。

フロントエンドから受け取るデータ形式が変化しても、
ルート層はこのサービスの I/F を呼ぶだけで済むように責務を分離している。
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.db.db import mysql_connection
from app.schemas.schemas import PaymentSplitRecord

FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1"


# 為替レート取得
# 外部APIアクセスをサービス側に隠蔽することで、フロント変更と切り離す。
def fetch_frankfurter_rates(
    *,
    base: str = "EUR",
    symbols: Optional[list[str]] = None,
    date: str = "latest",
) -> dict:
    params = {"base": base.upper()}
    if symbols:
        params["symbols"] = ",".join(symbol.upper() for symbol in symbols)

    normalized_date = date.lstrip("/")
    if normalized_date.startswith("v1/"):
        normalized_date = normalized_date[3:]

    url = f"{FRANKFURTER_BASE_URL}/{normalized_date}?{urlencode(params)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "warikan-app/1.0"})
    with urlopen(request, timeout=10) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)


# JPY 換算レート解決
# 登録時点で換算レートを固定化し、後日のレート変動で精算結果が変わるのを防ぐ。
def resolve_jpy_exchange_rate(currency_code: str) -> float:
    normalized_code = currency_code.upper()
    if normalized_code == "JPY":
        return 1.0

    response = fetch_frankfurter_rates(base=normalized_code, symbols=["JPY"])
    rates = response.get("rates") or {}
    jpy_rate = rates.get("JPY")
    if jpy_rate is None:
        raise ValueError(f"JPY exchange rate not found for currency: {normalized_code}")
    return float(jpy_rate)


# 支払い作成
# 戻り値を (成功可否, 結果) に統一し、ルート側のエラーハンドリングを単純化する。
def create_payment(
    group_id: int,
    login_user_name: str,
    title: str,
    amount_total: float,
    currency_code: str,
    exchange_rate: float,
    splits: List[Dict[str, Any]],
) -> Tuple[bool, int | str]:
    try:
        with mysql_connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO `payments` (group_id, paid_by_user_name, title, amount_total, currency_code, exchange_rate)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (group_id, login_user_name, title, amount_total, currency_code.upper(), exchange_rate),
                    )
                    payment_id = int(cur.lastrowid)

                    for split in splits:
                        cur.execute(
                            """
                            INSERT INTO `payment_splits` (payment_id, group_id, beneficiary_user_name, amount)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (payment_id, group_id, split["beneficiary_user_name"], split["amount"]),
                        )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except Exception as exc:
        return False, str(exc)

    return True, payment_id


# 支払い承認
# 現在ログイン中のユーザーが自分の分担のみ承認できるように条件を限定する。
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


# 支払い削除
# 作成者本人のみ削除可能にすることで、他ユーザーによる誤操作を防止する。
def delete_payment(group_id: int, payment_id: int, current_user_name: str) -> Tuple[bool, str]:
    try:
        with mysql_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM `payments`
                    WHERE payment_id = %s AND group_id = %s AND paid_by_user_name = %s
                    """,
                    (payment_id, group_id, current_user_name),
                )
                deleted_rows = cur.rowcount
            conn.commit()

        if deleted_rows == 0:
            return False, "削除対象が見つからないか、削除権限がありません。"
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


# グループ支払い一覧取得
# DB 正規化された明細を API 向けの読みやすい構造に整形して返却する。
def list_group_payments(group_id: int) -> List[Dict[str, Any]]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.payment_id,
                    p.paid_by_user_name,
                    p.title,
                    p.amount_total,
                    p.currency_code,
                    p.exchange_rate,
                    p.payment_date,
                    ps.beneficiary_user_name,
                    ps.amount,
                    ps.approved
                FROM `payments` p
                INNER JOIN `payment_splits` ps
                    ON p.payment_id = ps.payment_id
                WHERE p.group_id = %s
                ORDER BY p.payment_id DESC, ps.beneficiary_user_name ASC
                """,
                (group_id,),
            )
            rows = cur.fetchall()

    grouped: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        payment_id = int(row["payment_id"])
        if payment_id not in grouped:
            grouped[payment_id] = {
                "payment_id": payment_id,
                "paid_by_user_name": row["paid_by_user_name"],
                "title": row["title"],
                "amount_total": float(row["amount_total"]),
                "currency_code": row["currency_code"],
                "exchange_rate": float(row["exchange_rate"]),
                "payment_date": row["payment_date"].isoformat() if row["payment_date"] else None,
                "splits": [],
                "is_approved": True,
            }

        split = {
            "beneficiary_user_name": row["beneficiary_user_name"],
            "amount": float(row["amount"]),
            "approved": bool(row["approved"]),
        }
        grouped[payment_id]["splits"].append(split)
        if not split["approved"]:
            grouped[payment_id]["is_approved"] = False

    return list(grouped.values())


__all__ = [
    "create_payment",
    "delete_payment",
    "authenticate_payment_by_current_user",
    "resolve_jpy_exchange_rate",
    "list_group_payments",
    "fetch_frankfurter_rates",
]