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


def _minimize_settlements(net: Dict[str, Decimal]) -> List[Dict[str, str | float]]:
    creditors: List[Tuple[str, Decimal]] = sorted(
        [(name, amount) for name, amount in net.items() if amount > 0],
        key=lambda x: x[1],
        reverse=True,
    )
    debtors: List[Tuple[str, Decimal]] = sorted(
        [(name, -amount) for name, amount in net.items() if amount < 0],
        key=lambda x: x[1],
        reverse=True,
    )

    i = 0
    j = 0
    settlements: List[Dict[str, str | float]] = []

    while i < len(creditors) and j < len(debtors):
        creditor_name, creditor_amount = creditors[i]
        debtor_name, debtor_amount = debtors[j]
        transfer = min(creditor_amount, debtor_amount)

        settlements.append(
            {
                "from_user_name": debtor_name,
                "to_user_name": creditor_name,
                "amount": float(transfer),
            }
        )

        creditor_amount -= transfer
        debtor_amount -= transfer

        creditors[i] = (creditor_name, creditor_amount)
        debtors[j] = (debtor_name, debtor_amount)

        if creditor_amount == 0:
            i += 1
        if debtor_amount == 0:
            j += 1

    return settlements


def _fetch_approved_split_records(group_id: int) -> List[PaymentSplitRecord]:
    with mysql_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.payment_id,
                    p.paid_by_user_name,
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
        )
        for row in rows
    ]


def calculate_group_settlements(group_id: int) -> Dict[str, object]:
    records = _fetch_approved_split_records(group_id)

    net: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for record in records:
        net[record.payer] += record.amount
        net[record.beneficiary] -= record.amount

    settlements = _minimize_settlements(net)

    return {
        "group_id": group_id,
        "approved_payment_count": len({record.payment_id for record in records}),
        "settlements": settlements,
    }
