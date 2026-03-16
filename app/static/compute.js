// 認証情報とメンバー一覧（ページ初期化時にセッション API から取得する）
let CURRENT_GROUP_ID = null;
let CURRENT_GROUP = null;
let CURRENT_USER = null;
let MEMBER_NAMES = [];

const CURRENCY_OPTIONS = ["JPY", "USD", "EUR", "GBP"];
let payments = [];

// ページ読み込み時にセッション情報を取得してから初期化する
window.addEventListener('DOMContentLoaded', async () => {
    setupEventHandlers();
    await loadSessionInfo();
    initializeMemberSelectors();
    await loadPayments();
});

function setupEventHandlers() {
    const paymentForm = document.getElementById('payment-form');
    const settlementForm = document.getElementById('settlement-form');
    const addPayeeButton = document.getElementById('add-payee-btn');
    const payeeListContainer = document.getElementById('payeeListContainer');
    const unapprovedList = document.getElementById('unapprovedList');
    const approvedList = document.getElementById('approvedList');

    paymentForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        await registerPayment();
    });

    settlementForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        await calculateMinFlow();
    });

    addPayeeButton.addEventListener('click', addPayeeRow);

    payeeListContainer.addEventListener('click', (event) => {
        const deletePayeeButton = event.target.closest('[data-action="delete-payee"]');
        if (!deletePayeeButton) return;
        const row = deletePayeeButton.closest('.payee-row');
        if (row) row.remove();
    });

    const handlePaymentAction = async (event) => {
        const actionButton = event.target.closest('[data-action]');
        if (!actionButton) return;
        const paymentId = Number(actionButton.dataset.paymentId);
        if (!Number.isFinite(paymentId)) return;

        if (actionButton.dataset.action === 'approve') {
            await approvePayment(paymentId);
        } else if (actionButton.dataset.action === 'delete-payment') {
            await deletePayment(paymentId);
        }
    };

    unapprovedList.addEventListener('click', handlePaymentAction);
    approvedList.addEventListener('click', handlePaymentAction);
}

// --- 0. セッション情報の取得 ---
async function loadSessionInfo() {
    try {
        const response = await fetch('/register/me');
        if (!response.ok) {
            alert("You are not logged in. Please log in first.");
            window.location.href = "/";
            return;
        }
        const data = await response.json();
        CURRENT_GROUP_ID = data.group_id;
        CURRENT_GROUP = data.group_name;
        CURRENT_USER = data.user_name;

        document.getElementById('display-user').innerText = `User: ${CURRENT_USER}`;
        document.getElementById('display-group').innerText = `Group: ${CURRENT_GROUP}`;

        // メンバー一覧もサーバーから取得する
        const membersResponse = await fetch(`/payment/members`);
        if (membersResponse.ok) {
            const membersData = await membersResponse.json();
            MEMBER_NAMES = membersData.members || [];
        }
    } catch (e) {
        alert("Error: Failed to load session info");
        window.location.href = "/";
    }
}

// --- 1. バックエンドからのデータ取得 ---
async function loadPayments() {
    try {
        const response = await fetch(`/payment/list`);
        if (response.status === 401) {          // ← 先に401をチェック
            alert("You are not logged in. Please log in first.");
            window.location.href = "/";
            return;
        }
        if (!response.ok) throw new Error("Fail to load payments");
        const result = await response.json();
        payments = result.all || [];
        render();
    } catch (e) {
        console.error(e);
    }
}

function buildMemberOptions(includeEmpty = true) {
    const emptyOption = includeEmpty ? '<option value="">Please select</option>' : '';
    const memberOptions = MEMBER_NAMES.map(name => `<option value="${name}">${name}</option>`).join('');
    return `${emptyOption}${memberOptions}`;
}

function initializeMemberSelectors() {
    const payerSelect = document.getElementById('payer');
    payerSelect.innerHTML = CURRENT_USER;

    document.querySelectorAll('.p-name').forEach(select => {
        select.innerHTML = buildMemberOptions();
    });

    const currencySelect = document.getElementById('currency-select');
    currencySelect.innerHTML = CURRENCY_OPTIONS
        .map(code => `<option value="${code}">${code}</option>`)
        .join('');
    currencySelect.value = 'JPY';
}

function getCurrencySymbol(currencyCode) {
    const symbols = {
        JPY: '¥',
        USD: '$',
        EUR: '€',
        GBP: '£'
    };
    return symbols[currencyCode] || currencyCode;
}

function formatCurrencyAmount(amount, currencyCode) {
    const symbol = getCurrencySymbol(currencyCode);
    return `${amount}${symbol}`;
}

// --- 2. 支払い登録（POST） ---
async function registerPayment() {
    const payerName = CURRENT_USER;
    const nameInputs = document.querySelectorAll('.p-name');
    const amountInputs = document.querySelectorAll('.p-amount');

    let splits = [];
    let total = 0;

    nameInputs.forEach((el, i) => {
        const val = parseFloat(amountInputs[i].value);
        if (el.value && !isNaN(val)) {
            splits.push({ beneficiary_user_name: el.value, amount: val });
            total += val;
        }
    });

    const selectedCurrency = document.getElementById('currency-select').value || 'JPY';

    const title = document.getElementById('title').value;

    const newData = {
        group_id: CURRENT_GROUP_ID,
        title: title,
        amount_total: total,
        currency_code: selectedCurrency,
        splits: splits
    };

    try {
        const response = await fetch('/payment/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newData)
        });
        const result = await response.json();
        if (result.status === "success") {
            alert("Registered successfully");
            clearInput();
            await loadPayments();
        } else {
            alert("Error: " + (result.detail || "Failed to register"));
        }
    } catch (e) {
        alert("Fail to save");
    }
}

// --- 3. 承認処理（POST） ---
async function approvePayment(paymentId) {
    try {
        await fetch(`/payment/authenticate?payment_id=${paymentId}`, {
            method: 'POST',
        });
        await loadPayments();
    } catch (e) {
        alert("Fail to authenticate");
    }
}

// --- 4. 支払い削除（DELETE） ---
async function deletePayment(paymentId) {
    const confirmed = confirm("Delete this payment request?\n* Only the creator can delete it.");
    if (!confirmed) return;

    try {
        const response = await fetch(`/payment/${paymentId}`, {
            method: 'DELETE'
        });
        const result = await response.json();
        if (!response.ok || result.status !== 'success') {
            throw new Error(result.detail || 'Fail to delete');
        }
        await loadPayments();
    } catch (e) {
        alert(e.message || 'Fail to delete');
    }
}

// --- 5. 最小フロー精算計算（GET） ---
async function calculateMinFlow() {
    const outputDiv = document.getElementById('Output');
    outputDiv.innerText = "cumputing...";

    try {
        const response = await fetch(`/payment/settlements`);
        const result = await response.json();
        const settlements = result?.result?.settlements || [];
        outputDiv.innerText = settlements.length
            ? settlements
                .map(s => `${s.from_user_name} → ${s.to_user_name}: ${formatCurrencyAmount(s.amount, 'JPY')}`)
                .join('\n')
            : "No settlements needed.";
    } catch (e) {
        outputDiv.innerText = "Failed to retrieve settlement data.";
    }
}

// --- UI補助機能 ---
function addPayeeRow() {
    const container = document.getElementById('payeeListContainer');
    const div = document.createElement('div');
    div.className = 'payee-row';
    div.innerHTML = `
            <select class="p-name">${buildMemberOptions()}</select>
            <input type="number" class="p-amount" placeholder="Amount">
            <form class="inline-form">
                <button type="button" class="delete-btn" data-action="delete-payee">×</button>
            </form>
        `;
    container.appendChild(div);
}

function clearInput() {
    document.getElementById('payer').value = "";
    document.getElementById('currency-select').value = 'JPY';
    document.getElementById('payeeListContainer').innerHTML = `
            <div class="payee-row">
                <select class="p-name">${buildMemberOptions()}</select>
                <input type="number" class="p-amount" placeholder="Amount">
            </div>`;
}

function render() {
    const unapprovedUl = document.getElementById('unapprovedList');
    const approvedUl = document.getElementById('approvedList');
    unapprovedUl.innerHTML = "";
    approvedUl.innerHTML = "";

    payments.forEach(p => {
        const targetNames = p.splits.map(d => d.beneficiary_user_name);
        const approvedBy = p.splits.filter(d => d.approved).map(d => d.beneficiary_user_name);
        const isFullyApproved = p.is_approved;

        const li = document.createElement('li');
        const currencyCode = p.currency_code || 'JPY';
        const totalAmountText = formatCurrencyAmount(p.amount_total, currencyCode);
        const detailStr = p.splits
            .map(d => `${d.beneficiary_user_name}(${formatCurrencyAmount(d.amount, currencyCode)})`)
            .join(', ');

        // 自分の承認が必要か
        const needsMyApproval = targetNames.includes(CURRENT_USER) && !approvedBy.includes(CURRENT_USER);
        const approveButtonLabel = needsMyApproval ? 'Approve' : 'Pending';
        const approveDisabledAttr = needsMyApproval ? '' : 'disabled';

        let approvalActionHtml = `<span class="complete-message">✓ Complete</span>`;
        if (!isFullyApproved) {
            approvalActionHtml = `
                <form class="inline-form">
                    <button type="button" class="approve-btn" data-action="approve" data-payment-id="${p.payment_id}" ${approveDisabledAttr}>
                        ${approveButtonLabel}
                    </button>
                </form>`;
        }

        let deleteActionHtml = '';
        if (p.paid_by_user_name === CURRENT_USER) {
            deleteActionHtml = `
                <form class="inline-form">
                    <button type="button" class="delete-payment-btn" data-action="delete-payment" data-payment-id="${p.payment_id}">Delete</button>
                </form>`;
        }

        li.innerHTML = `
                <div class="main-info">
                    <span>${p.title}</span><br>
                    <span>${p.paid_by_user_name}</span> → ${totalAmountText}<br>

                    <small class="detail-text">Details: ${detailStr}</small><br>
                    <small class="approval-status">Approved: ${approvedBy.join(', ')}</small>
                </div>
                <div class="payment-actions">
                    ${approvalActionHtml}
                    ${deleteActionHtml}
                </div>
            `;

        if (isFullyApproved) {
            approvedUl.appendChild(li);
        } else {
            unapprovedUl.appendChild(li);
        }
    });
}
