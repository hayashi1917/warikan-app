import pandas as pd
from decimal import Decimal
from typing import List, Dict
from app.schemas.schemas import PaymentSplitRecord
"""
一応小数点以下も可
TSVの書式は　貸した人 (借りた人タプル) (金額タプル)
タプルの中はスペースなし
tsvファイルの書式などチェックしないので、

全部明細に出ているかチェックする。
総貸し量をもとの行列とをチェックする。
"""
pd.options.display.unicode.east_asian_width = True
def net_balances(matrix):
    return matrix.sum(axis=1) - matrix.sum(axis=0)

def min_flow(net_balances):
    c = net_balances[net_balances > 0].sort_values(ascending=False)
    d = net_balances[net_balances < 0].abs().sort_values(ascending=False)
    res = pd.DataFrame(Decimal('0'), index=net_balances.index, columns=net_balances.index)
    i, j = 0, 0
    while i < len(c) and j < len(d):
        amt = min(c.iloc[i], d.iloc[j])
        res.loc[c.index[i], d.index[j]] = amt
        c.iloc[i] -= amt
        d.iloc[j] -= amt
        if c.iloc[i] == 0: i += 1
        if d.iloc[j] == 0: j += 1
    return res

def print_matrix(matrix, title):
    print(f"\n--- {title} ---")
    m = matrix.copy().rename_axis(index='貸した人', columns='借りた人')
    print(m)
    print("総貸し料",net_balances(m))

def print_settlement_list(matrix2):
    print("\n--- 具体的な返金指示 ---")
    s = matrix2.stack()
    settlements = s[s > 0]
    settlements = settlements.sort_index(level=1)
    if settlements.empty:
        print("送金の必要はありません（相殺完了）。")
        return

    for (lender, borrower), amount in settlements.items():
        print(f"{borrower} → {lender}へ {amount} ")

def create_matrix(file_path):
    df = pd.read_csv(file_path, sep='\t', names=['貸した人', '借りた人', '金額'])
    for col in ['借りた人', '金額']:
        df[col] = df[col].astype(str).str.strip('() ').str.split(',')
    
    df = df.explode(['借りた人', '金額']).dropna()
    df['金額'] = df['金額'].apply(lambda x: Decimal(x.strip()))
    matrix = df.groupby(['貸した人', '借りた人'])['金額'].sum().unstack(fill_value=Decimal('0'))
    all_n = matrix.index.union(matrix.columns)
    matrix = matrix.reindex(index=all_n, columns=all_n, fill_value=Decimal('0'))
    matrix2 = min_flow(net_balances(matrix))

    print("\n--- 明細 ---", df.to_string(index=True), sep="\n")
    print_matrix(matrix, "元の行列")
    print_matrix(matrix2, "最小フロー")
    print_settlement_list(matrix2)

def settlement_matrix_to_list(matrix: pd.DataFrame) -> List[Dict[str, str]]:
    """
    最小フロー行列を API 向けの送金リストに変換する。

    matrix.loc[受け取る人, 支払う人] = 金額
    なので、
    支払う人 -> 受け取る人 の形に直す。
    """
    settlements: List[Dict[str, str]] = []

    stacked = matrix.stack()
    stacked = stacked[stacked > 0]

    for (receiver, payer), amount in stacked.items():
        settlements.append(
            {
                "from_user_name": payer,
                "to_user_name": receiver,
                "amount": str(amount),
            }
        )

    return settlements


def calculate_from_matrix(matrix: pd.DataFrame) -> Dict[str, object]:
    """
    支払い行列を受け取り、
    差額計算 → 最小送金行列 → 返金リスト をまとめて返す。
    """
    balance_series = net_balances(matrix)
    minimized_matrix = min_flow(balance_series)
    settlements = settlement_matrix_to_list(minimized_matrix)

    return {
        "net_balances": balance_series,
        "settlement_matrix": minimized_matrix,
        "settlements": settlements,
    }