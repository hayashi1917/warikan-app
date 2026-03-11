from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from app.db.db import mysql_connection
from app.services.payment import calculate_from_matrix
from app.schemas.schemas import PaymentSplitRecord
import pandas as pd

# def _minimize_settlements(net: Dict[str, Decimal]) -> List[Dict[str, str | float]]:
#     creditors: List[Tuple[str, Decimal]] = sorted(
#         [(name, amount) for name, amount in net.items() if amount > 0],
#         key=lambda x: x[1],
#         reverse=True,
#     )
#     debtors: List[Tuple[str, Decimal]] = sorted(
#         [(name, -amount) for name, amount in net.items() if amount < 0],
#         key=lambda x: x[1],
#         reverse=True,
#     )

#     i = 0
#     j = 0
#     settlements: List[Dict[str, str | float]] = []

#     while i < len(creditors) and j < len(debtors):
#         creditor_name, creditor_amount = creditors[i]
#         debtor_name, debtor_amount = debtors[j]
#         transfer = min(creditor_amount, debtor_amount)

#         settlements.append(
#             {
#                 "from_user_name": debtor_name,
#                 "to_user_name": creditor_name,
#                 "amount": float(transfer),
#             }
#         )

#         creditor_amount -= transfer
#         debtor_amount -= transfer

#         creditors[i] = (creditor_name, creditor_amount)
#         debtors[j] = (debtor_name, debtor_amount)

#         if creditor_amount == 0:
#             i += 1
#         if debtor_amount == 0:
#             j += 1

#     return settlements


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


# def calculate_group_settlements(group_id: int) -> Dict[str, object]:
#     records = _fetch_approved_split_records(group_id)

#     net: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
#     for record in records:
#         converted_amount = record.amount * record.exchange_rate
#         net[record.payer] += converted_amount
#         net[record.beneficiary] -= converted_amount

#     settlements = _minimize_settlements(net)

#     return {
#         "group_id": group_id,
#         "approved_payment_count": len({record.payment_id for record in records}),
#         "settlements": settlements,
#     }

def _build_payment_matrix(records: List[PaymentSplitRecord]) -> pd.DataFrame:
    """
    支払い明細を行列化する。

    行 = 貸した人(payer)
    列 = 借りた人(beneficiary)
    値 = payer が beneficiary のために立て替えた金額（基準通貨換算後）
    """
    all_names = sorted(
        {record.payer for record in records} |
        {record.beneficiary for record in records}
    )

    matrix = pd.DataFrame(
        Decimal("0"),
        index=all_names,
        columns=all_names,
    )

    for record in records:
        converted_amount = record.amount * record.exchange_rate
        matrix.loc[record.payer, record.beneficiary] += converted_amount

    return matrix


def calculate_group_settlements(group_id: int) -> Dict[str, object]:
    """
    グループ内の承認済み支払いをもとに、
    payment.py の行列ベースロジックで精算結果を返す。
    """
    records = _fetch_approved_split_records(group_id)

    if not records:
        return {
            "group_id": group_id,
            "approved_payment_count": 0,
            "settlements": [],
            "matrix": [],
        }

    # 支払い明細を行列化
    payment_matrix = _build_payment_matrix(records)

    # payment.py を呼び出して精算結果を作る
    payment_result = calculate_from_matrix(payment_matrix)

    return {
        "group_id": group_id,
        "approved_payment_count": len({record.payment_id for record in records}),
        "settlements": payment_result["settlements"],
        # 必要ならデバッグ用に行列も返せる
        "matrix": payment_matrix.to_dict(),
    }