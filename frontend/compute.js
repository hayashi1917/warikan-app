// 認証情報の取得（localStorageから）
const CURRENT_GROUP = localStorage.getItem('currentGroup');
const CURRENT_USER = localStorage.getItem('currentUser');
const ACCESS_TOKEN = localStorage.getItem('accessToken');

// ログインしていない場合は戻す
if (!CURRENT_GROUP || !CURRENT_USER || !ACCESS_TOKEN) {
    alert("You are not logged in. Please log in first.");
    window.location.href = "index.html"; 
}

document.getElementById('display-user').innerText = `User: ${CURRENT_USER}`;
document.getElementById('display-group').innerText = `Group: ${CURRENT_GROUP}`;
document.getElementById('payer').value = CURRENT_USER;

let payments = [];

// ページ読み込み時にデータを取得
window.onload = loadPayments;

// --- 1. バックエンドからのデータ取得 ---
async function loadPayments() {
    try {
        const response = await fetch(`/api/payments?groupID=${CURRENT_GROUP}`, {
            headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` },
        });
        if (response.status === 401) {
            alert("Error 401: Failed to authenticate. Please log in again.");
            localStorage.clear();
            window.location.href = "index.html";
            return;
        }
        payments = await response.json();
        render();
    } catch (e) {
        console.error(e);
        // 本番運用前はモックデータでテスト可能
    }
}

// --- 2. 支払い登録（POST） ---
async function registerPayment() {
    const nameInputs = document.querySelectorAll('.p-name');
    const amountInputs = document.querySelectorAll('.p-amount');
    
    let details = [];
    let total = 0;

    nameInputs.forEach((el, i) => {
        const val = parseFloat(amountInputs[i].value);
        if (el.value && !isNaN(val)) {
            details.push({ name: el.value, amount: val });
            total += val;
        }
    });

    if (!details.length) {
        alert("Please enter at least one valid name and amount.");
        return;
    }

    const newData = {
        group_id: Number(CURRENT_GROUP),
        title: `Payment Request by ${CURRENT_USER}`,
        amount_total: total,
        currency_code: "JPY",
        exchange_rate: 1,
        splits: details.map(d => ({
            beneficiary_user_name: d.name,
            amount: d.amount
        })),
    };


    try {
        const response = await fetch('/api/payment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json',
                        'Authorization': `Bearer ${ACCESS_TOKEN}`},
            body: JSON.stringify(newData)
        });
        if (response.status === 401) {
            alert("Error 401: Failed to authenticate. Please log in again.");
            localStorage.clear();
            window.location.href = "index.html";
            return;
        }
        if (!response.ok) {
            const body = await response.text();
            throw new Error(`Failed to authenticate : HTTP ${response.status} ${body}`);
        }
        clearInput();
        await loadPayments();
    } catch (e) {
        console.error(e);
        alert(`${e.message}`);
    }
}

// --- 3. 承認処理（POST） ---
async function approvePayment(paymentId) {
    try {
        const response = await fetch(`/api/payment/${paymentId}/approve`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` },
        });
        if (response.status === 401) {
            alert("Error 401: Failed to authenticate. Please log in again.");
            localStorage.clear();
            window.location.href = "index.html";
            return;
        }
        if (!response.ok) {
            const body = await response.text();
            throw new Error(`Failed to authenticate: HTTP ${response.status} ${body}`);
        }
        await loadPayments();
    } catch (e) {
        console.error(e);
        alert(`${e.message}`);
    }
}

// --- 4. 最小フロー計算（POST） ---
async function calculateMinFlow() {
    const outputDiv = document.getElementById('Output');
    outputDiv.innerText = "Calculating...";

    try {
        const response = await fetch(`/api/create-matrix?groupID=${CURRENT_GROUP}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' ,
                        'Authorization': `Bearer ${ACCESS_TOKEN}`,
            },
        });
        if (response.status === 401) {
            alert("Error 401: Failed to authenticate. Please log in again.");
            localStorage.clear();
            window.location.href = "index.html";
            return;
        }
        if (!response.ok) {
            const body = await response.text();
            throw new Error(`Failed to calculate: HTTP ${response.status} ${body}`);
        }
        const result = await response.json();
        outputDiv.innerText = result.instructions.join('\n') || "You are all settled up!";
    } catch (e) {
        outputDiv.innerText = `Failed to retrieve settlement results.\n${e.message}`;
    }
}

// --- UI補助機能 ---
function addPayeeRow() {
    const container = document.getElementById('payeeListContainer');
    const div = document.createElement('div');
    div.className = 'payee-row';
    div.innerHTML = `
        <input type="text" class="p-name" placeholder="Name">
        <input type="number" class="p-amount" placeholder="Amount"> Yen
        <button class="delete-btn" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(div);
}

function clearInput() {
    document.getElementById('payer').value = CURRENT_USER;
    document.getElementById('payeeListContainer').innerHTML = `
        <div class="payee-row">
            <input type="text" class="p-name" placeholder="Name">
            <input type="number" class="p-amount" placeholder="Amount"> Yen
        </div>`;
}

function render() {
    const unapprovedUl = document.getElementById('unapprovedList');
    const approvedUl = document.getElementById('approvedList');
    unapprovedUl.innerHTML = "";
    approvedUl.innerHTML = "";

    payments.forEach(p => {
        // 全員が承認したかチェック (detailsの全員がapprovedByに含まれているか)
        const targetNames = p.details.map(d => d.name);
        const isFullyApproved = targetNames.every(name => p.approvedBy.includes(name));

        const li = document.createElement('li');
        const detailStr = p.details.map(d => `${d.name}(${d.amount}Yen)`).join(', ');
        
        // 自分の承認が必要か
        const needsMyApproval = targetNames.includes(CURRENT_USER) && !p.approvedBy.includes(CURRENT_USER);

        li.innerHTML = `
            <div class="main-info">
                <span>${p.payer}</span> → ${p.total}Yen<br>
                <small class="detail-text">Details: ${detailStr}</small><br>
                <small class="approval-status">Approved: ${p.approvedBy.join(', ')}</small>
            </div>
            <div>
                ${!isFullyApproved ? 
                    `<button class="approve-btn" ${!needsMyApproval ? 'disabled' : ''} onclick="approvePayment(${p.id})">
                        ${needsMyApproval ? 'Approve' : 'Pending Approval'}
                    </button>` : 
                    `<span class="complete-message">✓ Complete</span>`
                }
            </div>
        `;

        if (isFullyApproved) {
            approvedUl.appendChild(li);
        } else {
            unapprovedUl.appendChild(li);
        }
    });
}
