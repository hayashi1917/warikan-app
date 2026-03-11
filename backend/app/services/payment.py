"""精算ロジック — ペアごとの相殺方式。

提供された payment.py の行列ベースのアプローチを DB 入力に適応させたもの。
各ペア間で貸借を相殺し、直接的な返済指示を生成する。

グローバル最小フロー最適化ではなく、ペアごとのネッティングを行うことで
元の貸借関係を保持した精算結果を返す。
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple


def build_matrix(
    records: List[Tuple[str, str, Decimal]],
) -> Tuple[List[str], Dict[Tuple[str, str], Decimal]]:
    """立て替え記録から貸借行列を構築する。

    Parameters
    ----------
    records:
        (payer, beneficiary, amount_jpy) のリスト。

    Returns
    -------
    (names, matrix)
        names: 全参加者名のソート済みリスト
        matrix: (lender, borrower) -> 合計金額 の辞書
    """
    names_set: set[str] = set()
    matrix: Dict[Tuple[str, str], Decimal] = defaultdict(lambda: Decimal("0"))

    for payer, beneficiary, amount in records:
        names_set.add(payer)
        names_set.add(beneficiary)
        matrix[(payer, beneficiary)] += amount

    names = sorted(names_set)
    return names, matrix


def pairwise_netting(
    names: List[str],
    matrix: Dict[Tuple[str, str], Decimal],
) -> List[Dict[str, str | float]]:
    """ペアごとに貸借を相殺し、精算リストを生成する。

    各ペア (i, j) について matrix[i][j] と matrix[j][i] を比較し、
    差額分だけ借り手側から貸し手側へ返済する指示を出す。

    Parameters
    ----------
    names:
        全参加者名のリスト
    matrix:
        (lender, borrower) -> 金額 の辞書

    Returns
    -------
    精算指示のリスト。各要素は {"from_user_name", "to_user_name", "amount"} の辞書。
    """
    settlements: List[Dict[str, str | float]] = []

    for i, name_i in enumerate(names):
        for j in range(i + 1, len(names)):
            name_j = names[j]
            # name_i が name_j に貸した金額
            i_to_j = matrix.get((name_i, name_j), Decimal("0"))
            # name_j が name_i に貸した金額
            j_to_i = matrix.get((name_j, name_i), Decimal("0"))

            net = i_to_j - j_to_i

            if net > 0:
                # name_j は name_i に net を返済する
                settlements.append(
                    {
                        "from_user_name": name_j,
                        "to_user_name": name_i,
                        "amount": float(net),
                    }
                )
            elif net < 0:
                # name_i は name_j に |net| を返済する
                settlements.append(
                    {
                        "from_user_name": name_i,
                        "to_user_name": name_j,
                        "amount": float(-net),
                    }
                )

    return settlements


def calculate_settlements(
    records: List[Tuple[str, str, Decimal]],
) -> List[Dict[str, str | float]]:
    """立て替え記録からペアごとの精算リストを計算する。

    Parameters
    ----------
    records:
        (payer, beneficiary, amount_jpy) のリスト。

    Returns
    -------
    精算指示のリスト。
    """
    names, matrix = build_matrix(records)
    return pairwise_netting(names, matrix)
