from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Tuple

from app.db.db import mysql_connection


@dataclass
class PaymentSplitRecord:
    payment_id: int
    payer: str
    beneficiary: str
    amount: Decimal
    exchange_rate: Decimal


def _pairwise_settlements(
    pairwise: Dict[Tuple[str, str], Decimal],
) -> List[Dict[str, str | float]]:
    settlements: List[Dict[str, str | float]] = []
    processed: set[Tuple[str, str]] = set()

    for (payer, beneficiary) in pairwise:
        pair = (min(payer, beneficiary), max(payer, beneficiary))
        if pair in processed:
            continue
        processed.add(pair)

        a, b = pair
        a_paid_for_b = pairwise.get((a, b), Decimal("0"))
        b_paid_for_a = pairwise.get((b, a), Decimal("0"))
        net = a_paid_for_b - b_paid_for_a

        if net > 0:
            settlements.append(
                {
                    "from_user_name": b,
                    "to_user_name": a,
                    "amount": float(net),
                }
            )
        elif net < 0:
            settlements.append(
                {
                    "from_user_name": a,
                    "to_user_name": b,
                    "amount": float(-net),
                }
            )

    return settlements


def _fetch_approved_split_records(group_id: int) -> List[PaymentSplitRecord]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.payment_id,
                    p.paid_by_user_name,
                    p.exchange_rate,
                    ps.beneficiary_user_name,
                    ps.amount
                FROM `payments` p
                INNER JOIN `payment_splits` ps
                    ON p.payment_id = ps.payment_id
                WHERE
                    p.group_id = %s
                    AND ps.group_id = %s
                    AND p.payment_id IN (
                        SELECT payment_id
                        FROM `payment_splits`
                        WHERE group_id = %s
                        GROUP BY payment_id
                        HAVING SUM(CASE WHEN approved = FALSE THEN 1 ELSE 0 END) = 0
                    )
                ORDER BY p.payment_id ASC
                """,
                (group_id, group_id, group_id),
            )
            rows = cur.fetchall()

    return [
        PaymentSplitRecord(
            payment_id=int(row["payment_id"]),
            payer=row["paid_by_user_name"],
            beneficiary=row["beneficiary_user_name"],
            amount=Decimal(str(row["amount"])),
            exchange_rate=Decimal(str(row["exchange_rate"])),
        )
        for row in rows
    ]


def calculate_group_settlements(group_id: int) -> Dict[str, object]:
    records = _fetch_approved_split_records(group_id)

    pairwise: Dict[Tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))
    for record in records:
        if record.payer != record.beneficiary:
            converted_amount = record.amount * record.exchange_rate
            pairwise[(record.payer, record.beneficiary)] += converted_amount

    settlements = _pairwise_settlements(pairwise)

    return {
        "group_id": group_id,
        "approved_payment_count": len({record.payment_id for record in records}),
        "settlements": settlements,
    }
