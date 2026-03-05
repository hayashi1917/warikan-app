import pandas as pd
from decimal import Decimal

from .db import get_payments
"""
一応小数点以下も可
TSVの書式は 貸した人 (借りた人タプル) (金額タプル)
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

"""
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
"""

def create_matrix(group_id: int) -> list[str]:
    rows = get_payments(group_id)

    payments_by_id = {}
    for row in rows:
        payment_id = int(row["payment_id"])
        payer = str(row["paid_by_user_name"])
        beneficiary = str(row["beneficiary_user_name"])
        amount = Decimal(str(row["amount"]))
        approved = bool(row["approved"])

        if payment_id not in payments_by_id:
            payments_by_id[payment_id] = {
                "payer": payer,
                "payer_approved": False,
                "approved_debts": [],
            }

        if beneficiary == payer and approved:
            payments_by_id[payment_id]["payer_approved"] = True
        elif beneficiary != payer and approved and amount > 0:
            payments_by_id[payment_id]["approved_debts"].append((beneficiary, amount))

    balances = {}
    for payment in payments_by_id.values():
        if not payment["payer_approved"]:
            continue
        payer = payment["payer"]
        for beneficiary, amount in payment["approved_debts"]:
            balances[payer] = balances.get(payer, Decimal("0")) + amount
            balances[beneficiary] = balances.get(beneficiary, Decimal("0")) - amount

    creditors = sorted(
        [(name, value) for name, value in balances.items() if value > 0],
        key=lambda x: x[1],
        reverse=True,
    )
    debtors = sorted(
        [(name, -value) for name, value in balances.items() if value < 0],
        key=lambda x: x[1],
        reverse=True,
    )

    instructions = []
    i = 0
    j = 0
    while i < len(creditors) and j < len(debtors):
        creditor_name, credit_amount = creditors[i]
        debtor_name, debt_amount = debtors[j]
        transfer = min(credit_amount, debt_amount)
        transfer_str = f"{transfer.quantize(Decimal('0.01')):f}"
        instructions.append(f"{debtor_name} -> {creditor_name}: {transfer_str} 円")

        credit_amount -= transfer
        debt_amount -= transfer
        creditors[i] = (creditor_name, credit_amount)
        debtors[j] = (debtor_name, debt_amount)

        if credit_amount == 0:
            i += 1
        if debt_amount == 0:
            j += 1

    if not instructions:
        return ["清算の必要はありません。"]
    return instructions
