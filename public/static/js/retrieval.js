/* Retrieval log: the shared "log a retrieval" sheet, and the log page. */

const RETRIEVER_KEY = 'freezer-retrieved-by';

/* ---- Logging a retrieval (used from the tube modals) ------ */

function openRetrievalModal(section, tubeId, label) {
    if (!tubeId) {
        showToast('Save the tube before logging a retrieval.', 'warning');
        return;
    }

    document.getElementById('retrieval-section').value = section;
    document.getElementById('retrieval-tube-id').value = tubeId;
    document.getElementById('retrieval-tube-label').textContent = label || '';
    document.getElementById('retrieval-purpose').value = '';
    document.getElementById('retrieval-notes').value = '';
    document.getElementById('retrieval-consumed').checked = false;

    // Same person usually logs several in a row, so remember the name.
    let who = '';
    try { who = localStorage.getItem(RETRIEVER_KEY) || ''; } catch (e) { /* private mode */ }
    document.getElementById('retrieval-by').value = who;

    bootstrap.Modal.getOrCreateInstance(document.getElementById('retrievalModal')).show();
}

async function saveRetrieval() {
    const who = document.getElementById('retrieval-by').value.trim();
    if (!who) {
        showToast('Put your name in so the log means something.', 'error');
        document.getElementById('retrieval-by').focus();
        return;
    }

    const payload = {
        section: document.getElementById('retrieval-section').value,
        tube_id: parseInt(document.getElementById('retrieval-tube-id').value, 10),
        retrieved_by: who,
        purpose: document.getElementById('retrieval-purpose').value.trim(),
        notes: document.getElementById('retrieval-notes').value.trim(),
        consumed: document.getElementById('retrieval-consumed').checked,
    };

    const button = document.getElementById('btn-retrieval-save');
    button.disabled = true;
    try {
        const result = await API.post('/api/retrievals', payload);
        try { localStorage.setItem(RETRIEVER_KEY, who); } catch (e) { /* private mode */ }

        showToast(result.tube_removed
            ? `Retrieval logged — ${result.tube_label} removed from the freezer`
            : `Retrieval logged — freeze-thaw now ${result.freeze_thaw_cycles}`);

        bootstrap.Modal.getInstance(document.getElementById('retrievalModal')).hide();

        // The page that opened this sheet still shows the tube as it was
        // before. Tell it what happened so it can catch up.
        document.dispatchEvent(new CustomEvent('retrievallogged', {
            detail: {
                section: payload.section,
                tubeId: payload.tube_id,
                tubeRemoved: Boolean(result.tube_removed),
                freezeThawCycles: result.freeze_thaw_cycles,
            },
        }));
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        button.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const save = document.getElementById('btn-retrieval-save');
    if (save) save.addEventListener('click', saveRetrieval);
});

/* ---- The log page ----------------------------------------- */

const logState = { offset: 0, limit: 50, section: '', q: '' };

async function initRetrievalPage() {
    document.querySelectorAll('[data-section]').forEach((btn) => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('[data-section]')
                .forEach((b) => b.classList.toggle('active', b === btn));
            logState.section = btn.dataset.section;
            logState.offset = 0;
            loadRetrievals();
        });
    });

    document.getElementById('retrieval-search').addEventListener('input', debounce(() => {
        logState.q = document.getElementById('retrieval-search').value.trim();
        logState.offset = 0;
        loadRetrievals();
    }, 250));

    document.getElementById('retrieval-prev').addEventListener('click', () => {
        logState.offset = Math.max(0, logState.offset - logState.limit);
        loadRetrievals();
    });
    document.getElementById('retrieval-next').addEventListener('click', () => {
        logState.offset += logState.limit;
        loadRetrievals();
    });

    await Promise.all([loadRetrievals(), loadRetrievalStats()]);
}

async function loadRetrievalStats() {
    try {
        const stats = await API.get('/api/stats/retrievals');
        document.getElementById('retrieval-total').textContent = stats.total;
        document.getElementById('retrieval-recent').textContent = stats.last_30_days;
        document.getElementById('retrieval-consumed-count').textContent = stats.consumed;
        document.getElementById('retrieval-people').textContent = stats.people;
    } catch (err) {
        console.error('Retrieval stats failed to load:', err);
    }
}

function formatWhen(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}

async function loadRetrievals() {
    const body = document.getElementById('retrieval-rows');
    const params = new URLSearchParams({
        limit: logState.limit, offset: logState.offset,
    });
    if (logState.section) params.set('section', logState.section);
    if (logState.q) params.set('q', logState.q);

    try {
        const data = await API.get(`/api/retrievals?${params}`);
        body.textContent = '';

        if (!data.entries.length) {
            body.innerHTML = `
                <tr><td colspan="6">
                    <div class="empty-state border-0">
                        <i class="bi bi-clipboard-x empty-icon"></i>
                        <div class="empty-title">Nothing logged yet</div>
                        <div class="empty-hint">
                            Open a tube from the Raptor Biobank or CLIPR Research pages
                            and use <strong>Log retrieval</strong>.
                        </div>
                    </div>
                </td></tr>`;
        } else {
            data.entries.forEach((entry) => body.appendChild(retrievalRow(entry)));
        }

        const from = data.total ? logState.offset + 1 : 0;
        const to = Math.min(logState.offset + logState.limit, data.total);
        document.getElementById('retrieval-count').textContent =
            data.total ? `${from}–${to} of ${data.total}` : '';

        const pager = document.getElementById('retrieval-pager');
        pager.hidden = data.total <= logState.limit;
        document.getElementById('retrieval-prev').disabled = logState.offset === 0;
        document.getElementById('retrieval-next').disabled =
            logState.offset + logState.limit >= data.total;
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function retrievalRow(entry) {
    const tr = document.createElement('tr');
    const location = [entry.box_label, entry.position_label].filter(Boolean).join(' · ');

    tr.innerHTML = `
        <td class="log-when">${escapeHtml(formatWhen(entry.retrieved_at))}</td>
        <td>
            <span class="log-tube">${escapeHtml(entry.tube_label)}</span>
            ${entry.consumed ? '<span class="log-flag">used up</span>' : ''}
            ${entry.species_name
                ? `<div class="log-sub">${escapeHtml(entry.species_name)}</div>` : ''}
        </td>
        <td class="log-sub">${escapeHtml(location)}</td>
        <td>${escapeHtml(entry.retrieved_by)}</td>
        <td>
            ${escapeHtml(entry.purpose || '')}
            ${entry.notes ? `<div class="log-sub">${escapeHtml(entry.notes)}</div>` : ''}
        </td>
        <td class="text-end"></td>`;

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn btn-sm btn-outline-danger border-0';
    remove.title = 'Remove this entry';
    remove.setAttribute('aria-label', `Remove log entry for ${entry.tube_label}`);
    remove.innerHTML = '<i class="bi bi-trash"></i>';
    remove.addEventListener('click', () => deleteRetrieval(entry));
    tr.querySelector('td:last-child').appendChild(remove);

    return tr;
}

async function deleteRetrieval(entry) {
    if (!confirm(`Remove the log entry for ${entry.tube_label}? `
                 + 'The freeze-thaw count on the tube is left as it is.')) return;
    try {
        await API.del(`/api/retrievals/${entry.id}`);
        showToast('Log entry removed');
        await Promise.all([loadRetrievals(), loadRetrievalStats()]);
    } catch (err) {
        showToast(err.message, 'error');
    }
}
