// 認証情報とメンバー一覧（ページ初期化時にセッション API から取得する）
let CURRENT_GROUP_ID = null;
let CURRENT_GROUP = null;
let CURRENT_USER = null;
let MEMBER_NAMES = [];

const CURRENCY_OPTIONS = ["JPY", "USD", "EUR", "GBP"];
let payments = [];

// HTMLファイルが読み込まれると、以下の4つの関数が実行されます。
// if browser is loaded, run the following functions
window.addEventListener('DOMContentLoaded', async () => {
    setupEventHandlers();
    await loadSessionInfo();
    initializeMemberSelectors();
    await loadPayments();
});

// この関数は、画面に表示されているボタンがクリックされたときの処理を設定します。
// HTMLに存在する、ボタンの要素等を取得し、addEventListenerでイベントを設定します。
// This function is to set up the event handlers for the buttons on the screen.
// This function gets the elements of the buttons on the screen and sets up event listeners for them.
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

// この関数は、セッションからログインしているユーザーのグループ、名前をバックエンドから取得し、画面に表示させます。
// グループメンバーの名前もバックエンドから取得し、メンバー選択のプルダウンメニューに表示させます。
// This function is to get the group and name of the logged-in user from the backend and display them on the screen.
// This function gets the names of the group members from the backend and displays them in the member selection dropdown menu.
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
  
// この関数は、バックエンドから支払いデータを取得し、画面に表示させます。
// もしログインしていない場合は、ログインページにリダイレクトします。
// render関数を呼び出し、支払いデータのHTMLを構成します
// This function gets the payment data from the backend and displays it on the screen.
// If the user is not logged in, it will redirect to the login page.
// This function calls the render function to construct the HTML of the payment data.
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

// この関数は、メンバー選択のプルダウンメニューに表示させるメンバーの名前を生成します。
// バックエンドから取得したメンバー一覧から、<option> タグを各メンバー名で生成して、返します。
// This function is to generate the names of the group members to be displayed in the member selection dropdown menu.
// It generates <option> tags with each member name from the member list obtained from the backend and returns them.
function buildMemberOptions(includeEmpty = true) {
    const emptyOption = includeEmpty ? '<option value="">Please select</option>' : '';
    const memberOptions = MEMBER_NAMES.map(name => `<option value="${name}">${name}</option>`).join('');
    return `${emptyOption}${memberOptions}`;
}

// この関数は、メンバー選択のプルダウンメニューを初期化します。
// This function is to initialize the member selection dropdown menu.
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

// この関数は、通貨コードから通貨記号を取得します。
// 通貨コードと通貨記号は、辞書型で定義されています。
// This function is to get the currency symbol from the currency code.
// The currency code and currency symbol are defined in a dictionary.
function getCurrencySymbol(currencyCode) {
    const symbols = {
        JPY: '¥',
        USD: '$',
        EUR: '€',
        GBP: '£'
    };
    return symbols[currencyCode] || currencyCode;
}

// この関数は、通貨コードから通貨記号を取得し、金額をフォーマットします。
// This function is to get the currency symbol from the currency code and format the amount.
function formatCurrencyAmount(amount, currencyCode) {
    const symbol = getCurrencySymbol(currencyCode);
    return `${amount}${symbol}`;
}

// この関数は、支払いデータをバックエンドに登録します。
// まず、建て替えられた人と、建て替え金額の情報をsplits配列に格納します.また、支払いの合計額を計算します。
// This function is to register the payment data to the backend.
// First, the people who will receive the payment and the amount of the payment are stored in the splits array.
async function registerPayment() {
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

    // 通貨、タイトルを取得します。
    // The currency and title are retrieved.
    const selectedCurrency = document.getElementById('currency-select').value || 'JPY';
    const title = document.getElementById('title').value;

    // バックエンドに送信するデータを構築します。
    // The data to be sent to the backend is constructed.
    const newData = {
        group_id: CURRENT_GROUP_ID,
        title: title,
        amount_total: total,
        currency_code: selectedCurrency,
        splits: splits
    };

    try {
        // バックエンドに送信し、データベースに保存されます。
        // The data is sent to the backend and saved in the database.
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

// この関数は、支払いデータを承認します。
// This function is to approve the payment data.
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

// この関数は、支払いデータを削除します。
// バックエンドに、削除するデータのIDを送信し、データベースから削除します。
// This function is to delete the payment data.
// The data is sent to the backend and deleted from the database.
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

// この関数は、最小フロー精算計算を行います。
// This function is to calculate the minimum flow settlement.
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

// この関数は、建て替えられた人を追加するボタンが押された時に呼び出されます。
// buildMemberOptions()関数を呼び出して、メンバー選択プルダウンメニューを生成します。
// 建て替えられた金額を入力する、inputタグを生成します。
// appendChild()関数を呼び出して、コンテナに新しい行を追加します。
// This function is called when the add payee button is clicked.
// It calls the buildMemberOptions() function to generate the member selection dropdown menu.
// It also generates an input tag to enter the amount of the payment.
// It appends the new row to the container.

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

// この関数は、入力欄をクリアします。
// 通貨選択を日本円に戻します。
// 建て替えられた人のリストを、コンテナに再描画します。
// This function is to clear the input fields.
// It resets the currency selection to Japanese Yen.
// It also redraws the list of payees in the container.
function clearInput() {
    document.getElementById('payer').value = "";
    document.getElementById('currency-select').value = 'JPY';
    document.getElementById('payeeListContainer').innerHTML = `
            <div class="payee-row">
                <select class="p-name">${buildMemberOptions()}</select>
                <input type="number" class="p-amount" placeholder="Amount">
            </div>`;
}
// この関数は、支払いデータを画面に表示します。
// This function is to display the payment data on the screen.
function render() {
    // ul tag for unapproved payments
    const unapprovedUl = document.getElementById('unapprovedList');
    // ul tag for approved payments
    const approvedUl = document.getElementById('approvedList');
    unapprovedUl.innerHTML = "";
    approvedUl.innerHTML = "";

    // 1つの支払い情報それぞれに対し、支払い者、承認者、通貨、合計金額、立て替えられた人と金額を取得します
    // For each payment information, get the payer, approver, currency, total amount, and the beneficiary and amount.
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

        // もし、その支払い情報に対して、ログインしているユーザーが承認していない場合は、承認ボタンを表示します
        // 承認していた場合は、[pending]と表示します
        // If the payment information does not have approval from the logged-in user, the approval button is displayed.
        // If the payment information has approval from the logged-in user, [pending] is displayed.
        const needsMyApproval = targetNames.includes(CURRENT_USER) && !approvedBy.includes(CURRENT_USER);
        const approveButtonLabel = needsMyApproval ? 'Approve' : 'Pending';
        const approveDisabledAttr = needsMyApproval ? '' : 'disabled';


        // もしその支払い情報の、立て替えられた人全てが承認している場合は、[complete]と表示します
        // If the payment information's all beneficiaries have approved it, [complete] is displayed.
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
        // もし、その支払い情報の、支払った人がログインしているユーザーと一致する場合は、削除ボタンを表示します
        // If the payment information's payer is the logged-in user, the delete button is displayed.
        if (p.paid_by_user_name === CURRENT_USER) {
            deleteActionHtml = `
                <form class="inline-form">
                    <button type="button" class="delete-payment-btn" data-action="delete-payment" data-payment-id="${p.payment_id}">Delete</button>
                </form>`;
        }

        // 支払い情報をまとめ、HTMLを構成します
        // It summarizes the payment information and constructs the HTML.
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

        // その支払い情報が承認されている場合は、approvedUlに追加します
        // If the payment information is approved, it is added to the approvedUl.
        if (isFullyApproved) {
            approvedUl.appendChild(li);
        } else {
            unapprovedUl.appendChild(li);
        }
    });
}
