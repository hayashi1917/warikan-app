// 認証情報の取得（localStorageから）
const CURRENT_GROUP = localStorage.getItem('currentGroup');
const CURRENT_USER = localStorage.getItem('currentUser');
const ACCESS_TOKEN = localStorage.getItem('accessToken');

// ログインしていない場合は戻す
if (!CURRENT_GROUP || !CURRENT_USER || !ACCESS_TOKEN) {
    alert("ログイン情報がありません。TOPページに戻ります。");
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
        if (!response.ok) {
            const body = await response.text();
            throw new Error(`データ取得失敗: HTTP ${response.status} ${body}`);
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
        alert("入力内容が不完全です");
        return;
    }

    const newData = {
        group_id: Number(CURRENT_GROUP),
        title: `支払い申請 by ${CURRENT_USER}`,
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
        if (!response.ok) {
            const body = await response.text();
            throw new Error(`保存失敗: HTTP ${response.status} ${body}`);
        }
        clearInput();
        await loadPayments();
    } catch (e) {
        console.error(e);
        alert(`保存に失敗しました。\n${e.message}`);
    }
}

// --- 3. 承認処理（POST） ---
async function approvePayment(paymentId) {
    try {
        const response = await fetch(`/api/payment/${paymentId}/approve`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${ACCESS_TOKEN}` },
        });
        if (!response.ok) {
            const body = await response.text();
            throw new Error(`承認失敗: HTTP ${response.status} ${body}`);
        }
        await loadPayments();
    } catch (e) {
        console.error(e);
        alert(`承認に失敗しました。\n${e.message}`);
    }
}

// --- 4. 最小フロー計算（POST） ---
async function calculateMinFlow() {
    const outputDiv = document.getElementById('Output');
    outputDiv.innerText = "計算中...";

    try {
        const response = await fetch(`/api/create-matrix?groupID=${CURRENT_GROUP}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' ,
                        'Authorization': `Bearer ${ACCESS_TOKEN}`,
            },
        });
        if (!response.ok) {
            const body = await response.text();
            throw new Error(`計算失敗: HTTP ${response.status} ${body}`);
        }
        const result = await response.json();
        outputDiv.innerText = result.instructions.join('\n') || "清算の必要はありません。";
    } catch (e) {
        outputDiv.innerText = `計算データの取得に失敗しました。\n${e.message}`;
    }
}

// --- UI補助機能 ---
function addPayeeRow() {
    const container = document.getElementById('payeeListContainer');
    const div = document.createElement('div');
    div.className = 'payee-row';
    div.innerHTML = `
        <input type="text" class="p-name" placeholder="名前">
        <input type="number" class="p-amount" placeholder="金額"> 円
        <button class="delete-btn" onclick="this.parentElement.remove()">×</button>
    `;
    container.appendChild(div);
}

function clearInput() {
    document.getElementById('payer').value = CURRENT_USER;
    document.getElementById('payeeListContainer').innerHTML = `
        <div class="payee-row">
            <input type="text" class="p-name" placeholder="名前">
            <input type="number" class="p-amount" placeholder="金額"> 円
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
        const detailStr = p.details.map(d => `${d.name}(${d.amount}円)`).join(', ');
        
        // 自分の承認が必要か
        const needsMyApproval = targetNames.includes(CURRENT_USER) && !p.approvedBy.includes(CURRENT_USER);

        li.innerHTML = `
            <div class="main-info">
                <span>${p.payer}</span> → ${p.total}円<br>
                <small class="detail-text">内訳: ${detailStr}</small><br>
                <small class="approval-status">承認済: ${p.approvedBy.join(', ')}</small>
            </div>
            <div>
                ${!isFullyApproved ? 
                    `<button class="approve-btn" ${!needsMyApproval ? 'disabled' : ''} onclick="approvePayment(${p.id})">
                        ${needsMyApproval ? '承認する' : '承認待ち'}
                    </button>` : 
                    `<span class="complete-message">✓ 完了</span>`
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
