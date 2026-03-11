"""Application-level service layer.

Database functions were moved to app.db.
This module re-exports them for backward compatibility.
"""

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
