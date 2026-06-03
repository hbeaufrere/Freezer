/* Shared utilities and API helpers */

const API = {
    async get(url) {
        const res = await fetch(url);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: res.statusText }));
            throw new Error(err.error || res.statusText);
        }
        return res.json();
    },

    async post(url, data) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || res.statusText);
        return body;
    },

    async put(url, data) {
        const res = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || res.statusText);
        return body;
    },

    async patch(url, data) {
        const res = await fetch(url, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || res.statusText);
        return body;
    },

    async del(url, data) {
        const opts = { method: 'DELETE' };
        if (data) {
            opts.headers = { 'Content-Type': 'application/json' };
            opts.body = JSON.stringify(data);
        }
        const res = await fetch(url, opts);
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || res.statusText);
        return body;
    }
};

/* Show the shared retrieval-prompt modal. onConfirm receives
   { retrieved_by, purpose }. */
function showRetrievalPrompt(title, description, onConfirm) {
    const modal = document.getElementById('retrievalPromptModal');
    if (!modal) { onConfirm({ retrieved_by: '', purpose: '' }); return; }

    document.getElementById('retrievalPromptTitle').textContent = title;
    document.getElementById('retrievalPromptDesc').textContent = description;

    const byInput = document.getElementById('retrieval-by');
    const purposeInput = document.getElementById('retrieval-purpose');
    const u = window.__CURRENT_USER__;
    byInput.value = u ? (u.full_name || u.email) : '';
    purposeInput.value = '';

    const bsModal = new bootstrap.Modal(modal);
    const oldBtn = document.getElementById('retrieval-confirm-btn');
    const newBtn = oldBtn.cloneNode(true);
    oldBtn.parentNode.replaceChild(newBtn, oldBtn);

    newBtn.addEventListener('click', () => {
        const retrieved_by = byInput.value.trim();
        const purpose = purposeInput.value.trim();
        bsModal.hide();
        onConfirm({ retrieved_by, purpose });
    });

    bsModal.show();
    setTimeout(() => purposeInput.focus(), 300);
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const id = 'toast-' + Date.now();
    const bgClass = type === 'error' ? 'bg-danger' : type === 'warning' ? 'bg-warning' : 'bg-success';
    const html = `
        <div id="${id}" class="toast align-items-center text-white ${bgClass} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
    const toastEl = document.getElementById(id);
    const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

const _ROW_LABELS = ['A','B','C','D','E','F','G','H','J','K'];
function positionLabel(row, col) {
    const letter = _ROW_LABELS[row - 1] || String.fromCharCode(64 + row);
    return `${letter}${col}`;
}

function debounce(fn, ms = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}
