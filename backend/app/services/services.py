import json
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.db.db import mysql_connection


FRANKFURTER_BASE_URL = "https://api.frankfurter.dev/v1"


def fetch_frankfurter_rates(
    *,
    base: str = "EUR",
    symbols: Optional[list[str]] = None,
    date: str = "latest",
) -> dict:
    """
    Fetch exchange rates from frankfurter.dev.
    Example:
      fetch_frankfurter_rates(base="EUR", symbols=["USD", "JPY"])
    """
    params = {"base": base.upper()}
    if symbols:
        params["symbols"] = ",".join(symbol.upper() for symbol in symbols)

    normalized_date = date.lstrip("/")
    if normalized_date.startswith("v1/"):
        normalized_date = normalized_date[3:]
    url = f"{FRANKFURTER_BASE_URL}/{normalized_date}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "curl/8.7.1",
        },
    )
    with urlopen(request, timeout=10) as response:
        data = response.read().decode("utf-8")
    return json.loads(data)

__all__ = [
    "create_payment",
    "authenticate_payment_by_current_user",
    "list_group_payments",
    "fetch_frankfurter_rates",
]

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
    try:
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
    except Exception as e:
        return False, str(e)
    return True, payment_id

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
