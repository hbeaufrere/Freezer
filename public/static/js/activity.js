/* The activity log page: one feed of everything that happened, retrievals
   included. The retrieval sheet and its delete live in retrieval.js. */

const actState = { offset: 0, limit: 50, section: '', kind: '', q: '' };

const KIND_LABELS = {
    added: ['Added', 'kind-added'], edited: ['Edited', 'kind-edited'], relabelled: ['Relabelled', 'kind-edited'],
    removed: ['Removed', 'kind-removed'], moved: ['Moved', 'kind-moved'], thawed: ['Freeze-thaw', 'kind-thawed'],
    retrieved: ['Retrieved', 'kind-retrieved'], consumed: ['Used up', 'kind-consumed'],
    box: ['Box', 'kind-box'], dropoff: ['Drop-off', 'kind-dropoff'], collected: ['Collected', 'kind-dropoff'],
    event: ['Freezer event', 'kind-event'],
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

    initFreezerEvents();
    await Promise.all([loadActivity(), loadActivityStats(), loadFreezerEvents()]);
}

/* ---- Whole-freezer events --------------------------------- */

function localDateTimeValue(d) {
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function initFreezerEvents() {
    const note = document.getElementById('event-note');
    note.addEventListener('input', () => {
        document.getElementById('event-note-left').textContent = 120 - note.value.length;
    });
    document.getElementById('btn-event-new').addEventListener('click', () => openEventModal(null));
    document.getElementById('btn-event-save').addEventListener('click', saveFreezerEvent);
    document.getElementById('eventModal').addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' && ev.target.id === 'event-note') { ev.preventDefault(); saveFreezerEvent(); }
    });
}

async function openEventModal(event) {
    document.getElementById('event-id').value = event ? event.id : '';
    document.getElementById('event-modal-title').textContent = event ? 'Edit freezer event' : 'Record a freezer event';
    document.getElementById('event-note').value = event ? event.note : '';
    document.getElementById('event-note-left').textContent = 120 - (event ? event.note.length : 0);
    document.getElementById('event-when').value = localDateTimeValue(event ? new Date(event.occurred_at) : new Date());
    document.getElementById('btn-event-save').innerHTML = event
        ? '<i class="bi bi-check-lg me-1"></i>Save' : '<i class="bi bi-check-lg me-1"></i>Record';
    const preview = document.getElementById('event-preview');
    if (event) {
        preview.textContent = `Already noted on ${event.raptor_tubes} raptor tubes, ${event.research_tubes} research tubes `
            + `and ${event.whole_boxes} whole boxes. Editing changes the words, not which samples carry them.`;
    } else {
        preview.textContent = 'Counting what is in the freezer…';
        try {
            const p = await API.get('/api/freezer-events/preview');
            preview.textContent = `This will be noted on ${p.raptor_tubes} raptor tubes, ${p.research_tubes} research tubes `
                + `and ${p.whole_boxes} whole boxes — everything in the freezer right now. Samples added later will not carry it.`;
        } catch (err) { preview.textContent = ''; }
    }
    bootstrap.Modal.getOrCreateInstance(document.getElementById('eventModal')).show();
    setTimeout(() => document.getElementById('event-note').focus(), 300);
}

async function saveFreezerEvent() {
    const id = document.getElementById('event-id').value;
    const note = document.getElementById('event-note').value.trim();
    if (!note) { showToast('Say what happened, in a few words.', 'error'); return; }
    const when = document.getElementById('event-when').value;
    const payload = { note, occurred_at: when ? new Date(when).toISOString() : '' };
    const button = document.getElementById('btn-event-save');
    button.disabled = true;
    try {
        const saved = id ? await API.put(`/api/freezer-events/${id}`, payload)
                         : await API.post('/api/freezer-events', payload);
        showToast(id ? 'Event updated'
            : `Noted on ${saved.raptor_tubes + saved.research_tubes} tubes and ${saved.whole_boxes} whole boxes`);
        bootstrap.Modal.getInstance(document.getElementById('eventModal')).hide();
        await Promise.all([loadFreezerEvents(), loadActivity()]);
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        button.disabled = false;
    }
}

async function loadFreezerEvents() {
    const host = document.getElementById('event-list');
    try {
        const events = await API.get('/api/freezer-events');
        host.textContent = '';
        if (!events.length) {
            host.innerHTML = '<div class="text-body-secondary small">No freezer events recorded. Good.</div>';
            return;
        }
        events.forEach((e) => {
            const row = document.createElement('div');
            row.className = 'event-row';
            const still = e.raptor_tubes + e.research_tubes;
            row.innerHTML = `
                <i class="bi bi-exclamation-triangle-fill event-row-icon"></i>
                <div class="event-row-body">
                    <div><span class="event-row-when">${escapeHtml(formatWhen(e.occurred_at))}</span>
                         <span class="event-row-note">${escapeHtml(e.note)}</span></div>
                    <div class="log-sub">Noted on ${still} tube${still === 1 ? '' : 's'} still in the freezer
                        and ${e.whole_boxes} whole box${e.whole_boxes === 1 ? '' : 'es'}${e.recorded_by ? ` · recorded by ${escapeHtml(e.recorded_by)}` : ''}</div>
                </div>
                <span class="event-row-tools"></span>`;
            const tools = row.querySelector('.event-row-tools');
            const edit = document.createElement('button');
            edit.type = 'button'; edit.className = 'btn btn-sm btn-outline-secondary border-0';
            edit.title = 'Edit the note or time'; edit.innerHTML = '<i class="bi bi-pencil"></i>';
            edit.addEventListener('click', () => openEventModal(e));
            const del = document.createElement('button');
            del.type = 'button'; del.className = 'btn btn-sm btn-outline-danger border-0';
            del.title = 'Remove this event and its note from every sample'; del.innerHTML = '<i class="bi bi-trash"></i>';
            del.addEventListener('click', async () => {
                if (!confirm(`Remove "${e.note}"?\n\nThe note disappears from every sample that carries it.`)) return;
                try {
                    await API.del(`/api/freezer-events/${e.id}`);
                    showToast('Event removed');
                    await Promise.all([loadFreezerEvents(), loadActivity()]);
                } catch (err) { showToast(err.message, 'error'); }
            });
            tools.append(edit, del);
            host.appendChild(row);
        });
    } catch (err) {
        host.innerHTML = `<div class="text-danger small">${escapeHtml(err.message)}</div>`;
    }
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
