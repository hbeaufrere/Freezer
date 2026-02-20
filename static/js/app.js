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

/**
 * Show the retrieval prompt modal and call onConfirm({ retrieved_by, purpose })
 * when the user confirms. Calls onCancel (if provided) if they dismiss.
 */
function showRetrievalPrompt(title, description, onConfirm, onCancel) {
    const modal = document.getElementById('retrievalPromptModal');
    if (!modal) {
        // Fallback if modal isn't present (shouldn't happen)
        onConfirm({ retrieved_by: '', purpose: '' });
        return;
    }

    document.getElementById('retrievalPromptTitle').textContent = title;
    document.getElementById('retrievalPromptDesc').textContent = description;
    document.getElementById('retrieval-by').value = '';
    document.getElementById('retrieval-purpose').value = '';

    const bsModal = new bootstrap.Modal(modal);

    const confirmBtn = document.getElementById('retrieval-confirm-btn');

    // Clean up previous listeners
    const newConfirmBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

    newConfirmBtn.addEventListener('click', () => {
        const retrieved_by = document.getElementById('retrieval-by').value.trim();
        const purpose = document.getElementById('retrieval-purpose').value.trim();
        bsModal.hide();
        onConfirm({ retrieved_by, purpose });
    });

    modal.addEventListener('hidden.bs.modal', function handler() {
        modal.removeEventListener('hidden.bs.modal', handler);
    });

    bsModal.show();
}

/* ── Rack naming ──────────────────────────────────────────── */

function openRackNameModal(rackId, currentName) {
    document.getElementById('rack-name-rack-id').value = rackId;
    document.getElementById('rack-name-input').value = currentName || '';

    const saveBtn = document.getElementById('rack-name-save-btn');
    const newSaveBtn = saveBtn.cloneNode(true);
    saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);

    newSaveBtn.addEventListener('click', async () => {
        const name = document.getElementById('rack-name-input').value.trim();
        const id = document.getElementById('rack-name-rack-id').value;
        try {
            await API.put(`/api/racks/${id}`, { name });
            bootstrap.Modal.getInstance(document.getElementById('rackNameModal')).hide();
            showToast(name ? `Rack name set to "${name}"` : 'Rack name cleared');
            // Refresh the sidebar/freezer view if a refresh function is available
            if (typeof refreshFreezerView === 'function') refreshFreezerView();
        } catch (err) {
            showToast('Error saving rack name: ' + err.message, 'error');
        }
    });

    new bootstrap.Modal(document.getElementById('rackNameModal')).show();
}
