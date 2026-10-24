/* The activity log page: one feed of everything that happened, retrievals
   included. The retrieval sheet and its delete live in retrieval.js. */

const actState = { offset: 0, limit: 50, section: '', kind: '', q: '' };

const KIND_LABELS = {
    added: ['Added', 'kind-added'], edited: ['Edited', 'kind-edited'], relabelled: ['Relabelled', 'kind-edited'],
    removed: ['Removed', 'kind-removed'], moved: ['Moved', 'kind-moved'], thawed: ['Freeze-thaw', 'kind-thawed'],
    retrieved: ['Retrieved', 'kind-retrieved'], consumed: ['Used up', 'kind-consumed'],
    box: ['Box', 'kind-box'], dropoff: ['Drop-off', 'kind-dropoff'], collected: ['Collected', 'kind-dropoff'],
};

async function initActivityPage() {
    const who = document.getElementById('who-am-i');
    try { who.value = localStorage.getItem(RETRIEVER_KEY) || ''; } catch (e) { /* private mode */ }
    who.addEventListener('change', () => {
        try { localStorage.setItem(RETRIEVER_KEY, who.value.trim()); } catch (e) { /* private mode */ }
        showToast(who.value.trim() ? `Signing as ${who.value.trim()}` : 'Not signing entries');
    });

    document.querySelectorAll('[data-section]').forEach((btn) => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('[data-section]').forEach((b) => b.classList.toggle('active', b === btn));
            actState.section = btn.dataset.section; actState.offset = 0; loadActivity();
        });
    });
    document.getElementById('activity-kind').addEventListener('change', (e) => {
        actState.kind = e.target.value; actState.offset = 0; loadActivity();
    });
    document.getElementById('activity-search').addEventListener('input', debounce(() => {
        actState.q = document.getElementById('activity-search').value.trim(); actState.offset = 0; loadActivity();
    }, 250));
    document.getElementById('activity-prev').addEventListener('click', () => {
        actState.offset = Math.max(0, actState.offset - actState.limit); loadActivity();
    });
    document.getElementById('activity-next').addEventListener('click', () => {
        actState.offset += actState.limit; loadActivity();
    });

    await Promise.all([loadActivity(), loadActivityStats()]);
}

async function loadActivityStats() {
    try {
        const s = await API.get('/api/stats/activity');
        document.getElementById('act-added').textContent = s.added_30;
        document.getElementById('act-retrieved').textContent = s.retrieved_30;
        document.getElementById('act-moved').textContent = s.moved_30;
        document.getElementById('act-consumed').textContent = s.consumed;
    } catch (err) { console.error('Activity stats failed to load:', err); }
}

async function loadActivity() {
    const body = document.getElementById('activity-rows');
    const params = new URLSearchParams({ limit: actState.limit, offset: actState.offset });
    if (actState.section) params.set('section', actState.section);
    if (actState.kind) params.set('kind', actState.kind);
    if (actState.q) params.set('q', actState.q);

    try {
        const data = await API.get(`/api/activity?${params}`);
        body.textContent = '';
        if (!data.entries.length) {
            body.innerHTML = `
                <tr><td colspan="7">
                    <div class="empty-state border-0">
                        <i class="bi bi-journal empty-icon"></i>
                        <div class="empty-title">Nothing here yet</div>
                        <div class="empty-hint">Tubes added, moved, retrieved or removed will show up here.</div>
                    </div>
                </td></tr>`;
        } else {
            data.entries.forEach((e) => body.appendChild(activityRow(e)));
        }
        const from = data.total ? actState.offset + 1 : 0;
        const to = Math.min(actState.offset + actState.limit, data.total);
        document.getElementById('activity-count').textContent = data.total ? `${from}–${to} of ${data.total}` : '';
        document.getElementById('activity-pager').hidden = data.total <= actState.limit;
        document.getElementById('activity-prev').disabled = actState.offset === 0;
        document.getElementById('activity-next').disabled = actState.offset + actState.limit >= data.total;
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function activityRow(e) {
    const tr = document.createElement('tr');
    const [label, cls] = KIND_LABELS[e.kind] || [e.kind, ''];
    const where = [e.box_label, e.position_label].filter(Boolean).join(' · ');
    tr.innerHTML = `
        <td class="log-when">${escapeHtml(formatWhen(e.at))}</td>
        <td><span class="kind-badge ${cls}">${escapeHtml(label)}</span></td>
        <td>
            ${e.tube_label ? `<span class="log-tube">${escapeHtml(e.tube_label)}</span>` : '<span class="text-body-secondary">—</span>'}
            ${e.species_name ? `<div class="log-sub">${escapeHtml(e.species_name)}</div>` : ''}
        </td>
        <td class="log-sub">${escapeHtml(where)}</td>
        <td>${escapeHtml(e.actor || '')}</td>
        <td class="log-detail">${escapeHtml(e.detail || '')}</td>
        <td class="text-end"></td>`;

    // Only a retrieval can be struck from the log: it is a claim about a
    // person. Everything else is a record of what the database did.
    if (e.source === 'retrieval') {
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'btn btn-sm btn-outline-danger border-0';
        remove.title = 'Remove this retrieval entry';
        remove.setAttribute('aria-label', `Remove retrieval entry for ${e.tube_label}`);
        remove.innerHTML = '<i class="bi bi-trash"></i>';
        remove.addEventListener('click', async () => {
            if (!confirm(`Remove the retrieval entry for ${e.tube_label}? The freeze-thaw count on the tube is left as it is.`)) return;
            try {
                await API.del(`/api/retrievals/${e.id}`);
                showToast('Entry removed');
                await Promise.all([loadActivity(), loadActivityStats()]);
            } catch (err) { showToast(err.message, 'error'); }
        });
        tr.querySelector('td:last-child').appendChild(remove);
    }
    return tr;
}
