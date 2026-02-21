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
        updateStats(data.entries, data.total);
        updatePagination();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-3">Failed to load: ${err.message}</td></tr>`;
    }
}

function renderLogEntries(entries) {
    const tbody = document.getElementById('log-body');

    if (entries.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No entries found.</td></tr>`;
        return;
    }

    tbody.innerHTML = entries.map(e => {
        const ts = formatTimestamp(e.timestamp);
        const sectionBadge = e.section === 'raptor'
            ? '<span class="badge bg-primary">Raptor</span>'
            : '<span class="badge bg-success">Research</span>';
        const actionBadge = e.action === 'removed'
            ? '<span class="badge bg-danger">Removed</span>'
            : '<span class="badge bg-warning text-dark">Freeze-thaw</span>';
        const by = e.retrieved_by ? escHtml(e.retrieved_by) : '<span class="text-muted">—</span>';
        const purpose = e.purpose ? escHtml(e.purpose) : '<span class="text-muted">—</span>';
        const location = e.tube_info ? `<small class="text-muted">${escHtml(e.tube_info)}</small>` : '<span class="text-muted">—</span>';

        return `<tr>
            <td><small class="text-muted">${ts}</small></td>
            <td>${sectionBadge}</td>
            <td><strong>${escHtml(e.tube_identifier)}</strong></td>
            <td>${actionBadge}</td>
            <td>${by}</td>
            <td>${purpose}</td>
            <td>${location}</td>
            <td><button class="btn btn-outline-danger btn-sm py-0 px-1" title="Delete entry" onclick="deleteLogEntry(${e.id}, this)"><i class="bi bi-trash"></i></button></td>
        </tr>`;
    }).join('');
}

function updateStats(entries, total) {
    document.getElementById('log-stat-total').textContent = `${total.toLocaleString()} entries`;

    // Count from visible page for context (full counts would need separate queries)
    const section = document.getElementById('filter-section').value;
    const action = document.getElementById('filter-action').value;

    if (!action) {
        const removed = entries.filter(e => e.action === 'removed').length;
        const thawed = entries.filter(e => e.action === 'thawed').length;
        // Show partial counts from current page only when unfiltered
        document.getElementById('log-stat-removed').textContent =
            (logOffset === 0 && entries.length < LOG_PAGE_SIZE) ? `${removed} removed` : `${removed}+ removed`;
        document.getElementById('log-stat-thawed').textContent =
            (logOffset === 0 && entries.length < LOG_PAGE_SIZE) ? `${thawed} freeze-thaw` : `${thawed}+ freeze-thaw`;
    } else {
        document.getElementById('log-stat-removed').textContent = action === 'removed' ? `${total} removed` : '— removed';
        document.getElementById('log-stat-thawed').textContent = action === 'thawed' ? `${total} freeze-thaw` : '— freeze-thaw';
    }
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
        // ts is ISO-like: "2026-02-20 14:35:00" from SQLite
        const d = new Date(ts.replace(' ', 'T') + 'Z');
        return d.toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch {
        return ts;
    }
}

async function deleteLogEntry(entryId, btn) {
    if (!confirm('Delete this log entry? This cannot be undone.')) return;
    btn.disabled = true;
    try {
        await API.del(`/api/retrieval-log/${entryId}`);
        btn.closest('tr').remove();
        logTotal = Math.max(0, logTotal - 1);
        updateStats([], logTotal);
        updatePagination();
    } catch (err) {
        alert(`Failed to delete entry: ${err.message}`);
        btn.disabled = false;
    }
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
