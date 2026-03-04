import json
from typing import Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .db import (
    authenticate_user,
    create_group_with_leader,
    create_payment,
    create_user,
    ensure_schema,
    get_user,
    hash_password,
    mysql_connection,
    verify_password,
)


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
    "mysql_connection",
    "ensure_schema",
    "create_group_with_leader",
    "create_user",
    "get_user",
    "authenticate_user",
    "hash_password",
    "verify_password",
    "create_payment",
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