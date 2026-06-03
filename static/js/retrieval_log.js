/* Retrieval Log page logic */

const LOG_PAGE_SIZE = 100;
let logOffset = 0;
let logTotal = 0;

function initRetrievalLogPage() {
    document.getElementById('filter-section').addEventListener('change', () => { logOffset = 0; loadLog(); });
    document.getElementById('filter-action').addEventListener('change', () => { logOffset = 0; loadLog(); });
    document.getElementById('filter-search').addEventListener('input', debounce(() => { logOffset = 0; loadLog(); }, 300));
    document.getElementById('log-prev-btn').addEventListener('click', () => {
        if (logOffset >= LOG_PAGE_SIZE) { logOffset -= LOG_PAGE_SIZE; loadLog(); }
    });
    document.getElementById('log-next-btn').addEventListener('click', () => {
        if (logOffset + LOG_PAGE_SIZE < logTotal) { logOffset += LOG_PAGE_SIZE; loadLog(); }
    });

    document.getElementById('log-body').addEventListener('click', async (e) => {
        const btn = e.target.closest('button[data-action="delete-entry"]');
        if (!btn) return;
        if (!confirm('Delete this log entry? This cannot be undone.')) return;
        try {
            await API.del(`/api/retrieval-log/${btn.dataset.entryId}`);
            showToast('Entry deleted', 'success');
            loadLog();
        } catch (err) {
            showToast('Delete failed: ' + err.message, 'error');
        }
    });

    loadLog();
}

async function loadLog() {
    const section = document.getElementById('filter-section').value;
    const action = document.getElementById('filter-action').value;
    const q = document.getElementById('filter-search').value.trim();

    const params = new URLSearchParams({ limit: LOG_PAGE_SIZE, offset: logOffset });
    if (section) params.set('section', section);
    if (action) params.set('action', action);
    if (q) params.set('q', q);

    const tbody = document.getElementById('log-body');
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-3">
        <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>Loading...</td></tr>`;

    try {
        const data = await API.get(`/api/retrieval-log?${params}`);
        logTotal = data.total;
        renderLogEntries(data.entries);
        document.getElementById('log-stat-total').textContent =
            `${data.total.toLocaleString()} ${data.total === 1 ? 'entry' : 'entries'}`;
        updatePagination();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-3">Failed to load: ${err.message}</td></tr>`;
    }
}

function renderLogEntries(entries) {
    const tbody = document.getElementById('log-body');
    const adminCol = window.__IS_ADMIN__;

    if (entries.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-5">No entries match these filters.</td></tr>`;
        return;
    }

    tbody.innerHTML = entries.map(e => {
        const ts = formatTimestamp(e.timestamp);
        const sectionBadge = e.section === 'raptor'
            ? '<span class="badge text-bg-primary">Raptor</span>'
            : '<span class="badge text-bg-success">Research</span>';
        const actionBadge = e.action === 'removed'
            ? '<span class="badge text-bg-danger">Removed</span>'
            : '<span class="badge text-bg-warning">Freeze-thaw</span>';
        const by = e.retrieved_by ? escHtml(e.retrieved_by) : '<span class="text-muted">—</span>';
        const purpose = e.purpose ? escHtml(e.purpose) : '<span class="text-muted">—</span>';
        const location = e.tube_info ? `<small class="text-muted">${escHtml(e.tube_info)}</small>` : '<span class="text-muted">—</span>';
        const deleteBtn = adminCol
            ? `<td class="text-end"><button class="btn btn-sm btn-outline-danger" data-action="delete-entry" data-entry-id="${e.id}" title="Delete entry"><i class="bi bi-trash"></i></button></td>`
            : '';
        return `<tr>
            <td><small class="text-muted">${ts}</small></td>
            <td>${sectionBadge}</td>
            <td><strong>${escHtml(e.tube_identifier)}</strong></td>
            <td>${actionBadge}</td>
            <td>${by}</td>
            <td>${purpose}</td>
            <td>${location}</td>
            ${deleteBtn}
        </tr>`;
    }).join('');
}

function updatePagination() {
    const paginationEl = document.getElementById('log-pagination');
    const prevBtn = document.getElementById('log-prev-btn');
    const nextBtn = document.getElementById('log-next-btn');
    const pageInfo = document.getElementById('log-page-info');

    const start = logTotal === 0 ? 0 : logOffset + 1;
    const end = Math.min(logOffset + LOG_PAGE_SIZE, logTotal);

    pageInfo.textContent = logTotal > 0
        ? `Showing ${start}–${end} of ${logTotal.toLocaleString()}`
        : 'No entries';

    prevBtn.disabled = logOffset === 0;
    nextBtn.disabled = logOffset + LOG_PAGE_SIZE >= logTotal;

    paginationEl.style.display = logTotal > LOG_PAGE_SIZE ? '' : 'none';
}

function formatTimestamp(ts) {
    if (!ts) return '—';
    try {
        const d = new Date(ts);
        return d.toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch { return ts; }
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
