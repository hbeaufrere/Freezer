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

    async del(url) {
        const res = await fetch(url, { method: 'DELETE' });
        const body = await res.json();
        if (!res.ok) throw new Error(body.error || res.statusText);
        return body;
    }
};

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
