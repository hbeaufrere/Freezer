/* Statistics, CLIPR research: find samples, and the whole inventory as a
   tree. Both are read straight from the server; the count, the list and the
   downloads share one query there, so they cannot disagree. */

const rfilter = { q: '', rack_id: '', date_from: '', date_to: '' };
const RFILTER_FIELDS = {
    q: 'rfilter-q', rack_id: 'rfilter-rack', date_from: 'rfilter-from', date_to: 'rfilter-to',
};

let researchSelection = null;

async function initResearchFilter() {
    if (!document.getElementById('research-filter')) return;

    researchSelection = makeSelection({
        section: 'research', prefix: 'rfilter',
        tableHost: document.getElementById('rfilter-results'),
        onDone: runResearchFilter,
    });

    try {
        const options = await API.get('/api/research/filter-options');
        const select = document.getElementById('rfilter-rack');
        options.racks.forEach((r) => {
            const label = r.designation ? `${r.label} — ${r.designation}` : r.label;
            select.appendChild(new Option(`${label} · ${r.count}`, r.id));
        });
    } catch (err) {
        showToast(err.message, 'error');
    }

    Object.entries(RFILTER_FIELDS).forEach(([field, id]) => {
        const el = document.getElementById(id);
        const handler = () => { rfilter[field] = el.value.trim(); researchSelection?.clear(); runResearchFilter(); };
        el.addEventListener(field === 'q' ? 'input' : 'change', field === 'q' ? debounce(handler, 250) : handler);
    });
    document.getElementById('btn-rfilter-clear').addEventListener('click', () => {
        Object.entries(RFILTER_FIELDS).forEach(([field, id]) => {
            rfilter[field] = ''; document.getElementById(id).value = '';
        });
        runResearchFilter();
    });
    document.getElementById('btn-rfilter-csv').addEventListener('click', () => downloadResearchFiltered('csv'));
    document.getElementById('btn-rfilter-xlsx').addEventListener('click', () => downloadResearchFiltered('xlsx'));

    runResearchFilter();
}

function rfilterParams() {
    const params = new URLSearchParams();
    Object.entries(rfilter).forEach(([k, v]) => { if (v) params.set(k, v); });
    return params;
}

async function runResearchFilter() {
    const results = document.getElementById('rfilter-results');
    const note = document.getElementById('rfilter-note');
    let data;
    try {
        data = await API.get(`/api/research/filter?${rfilterParams()}`);
    } catch (err) {
        showToast(err.message, 'error'); return;
    }

    document.getElementById('rfilter-count').textContent = data.tubes.toLocaleString();
    document.getElementById('rfilter-count-label').textContent =
        `${data.tubes === 1 ? 'tube' : 'tubes'} in ${data.matched.toLocaleString()} `
        + `${data.matched === 1 ? 'entry' : 'entries'}`;

    const empty = data.matched === 0;
    document.getElementById('btn-rfilter-csv').disabled = empty;
    document.getElementById('btn-rfilter-xlsx').disabled = empty;

    if (empty) {
        results.innerHTML = `
            <div class="empty-state border-0 py-4">
                <i class="bi bi-search empty-icon"></i>
                <div class="empty-title">Nothing matches</div>
                <div class="empty-hint">Try fewer words, or clear the filter.</div>
            </div>`;
        note.hidden = true;
        return;
    }

    results.innerHTML = `
        <table class="table table-sm align-middle filter-table">
            <thead><tr>
                ${pickHeaderCell()}
                <th>Sample ID</th><th>Description</th><th>Tubes</th><th>Stored</th>
                <th>F/T</th><th>Where it is</th>
            </tr></thead>
            <tbody>${data.samples.map(rfilterRow).join('')}</tbody>
        </table>`;
    researchSelection?.wire();
    note.hidden = data.showing >= data.matched;
    note.textContent = `Showing the first ${data.showing.toLocaleString()} of `
        + `${data.matched.toLocaleString()}. The download has all of them.`;
}

function rfilterRow(s) {
    const place = [s.shelf, s.rack, s.drawer, s.box, s.position].filter(Boolean).join(' › ');
    const id = s.kind === 'bulk_box'
        ? `<i class="bi bi-box-seam me-1"></i>${escapeHtml(s.box)} <span class="result-kind">whole box</span>`
        : escapeHtml(s.sample_id || 'Untitled');
    return `<tr>
        ${pickCell(s.kind === 'tube' ? s.id : null, s.sample_id || 'Untitled')}
        <td class="filter-tube"><a href="/research?box=${s.box_id}">${id}</a></td>
        <td>${escapeHtml(s.description || '')}</td>
        <td>${s.tubes}</td>
        <td>${escapeHtml(s.date_stored || '')}</td>
        <td>${s.freeze_thaw_cycles ?? ''}</td>
        <td class="filter-where">${escapeHtml(place)}</td>
    </tr>`;
}

function downloadResearchFiltered(format) {
    const params = rfilterParams().toString();
    window.location.href = `/api/export/research/${format}${params ? '?' + params : ''}`;
}

/* ---- The inventory tree ------------------------------------ */

/* Native <details>, nested four deep. Each level folds on its own, remembers
   nothing, and needs no script to work — the buttons only open or close them
   all at once. Empty units are shown folded and muted rather than hidden, so
   an empty drawer reads as "empty", not "missing". */
async function initResearchInventory() {
    const body = document.getElementById('inventory-body');
    if (!body) return;

    let inv;
    try {
        inv = await API.get('/api/research/inventory');
    } catch (err) {
        body.innerHTML = `<div class="empty-state border-0"><div class="empty-hint">${escapeHtml(err.message)}</div></div>`;
        return;
    }

    const unit = (level, label, count, extra, inner, open) => `
        <details class="inv inv-${level}"${open ? ' open' : ''}>
            <summary>
                <span class="inv-label">${escapeHtml(label)}</span>
                ${extra ? `<span class="inv-extra">${escapeHtml(extra)}</span>` : ''}
                <span class="inv-count${count ? '' : ' is-empty'}">${count ? `${count} ${count === 1 ? 'tube' : 'tubes'}` : 'empty'}</span>
            </summary>
            <div class="inv-body">${inner}</div>
        </details>`;

    const boxHtml = (b) => {
        let inner;
        if (b.box_type === 'bulk') {
            const what = [b.bulk_sample_type, b.bulk_study].filter(Boolean).join(' — ') || 'contents not described';
            const full = b.bulk_kind === 'other' && b.bulk_fullness != null ? ` · about ${b.bulk_fullness}% full` : '';
            inner = `<div class="inv-bulk"><i class="bi bi-box-seam me-1"></i>Whole box: ${escapeHtml(what)}${full}</div>`;
        } else if (!b.samples.length) {
            inner = '<div class="inv-none">Nothing in this box.</div>';
        } else {
            inner = `<table class="table table-sm inv-table"><tbody>${b.samples.map((t) => `
                <tr>
                    <td class="inv-pos">${escapeHtml(t.position || '—')}</td>
                    <td class="filter-tube">${escapeHtml(t.sample_id || 'Untitled')}</td>
                    <td class="inv-desc">${escapeHtml(t.description || '')}</td>
                    <td class="inv-date">${escapeHtml(t.date_stored || '')}</td>
                </tr>`).join('')}</tbody></table>`;
        }
        const kind = b.box_type === 'bulk' ? 'whole box' : (b.box_type === 'plain' ? 'plain box' : '');
        return unit('box', b.label, b.count, kind, inner, false);
    };

    body.innerHTML = inv.shelves.map((sh) => unit('shelf', sh.name, sh.count, '',
        sh.racks.map((r) => unit('rack', r.label, r.count, r.designation || '',
            r.drawers.map((d) => unit('drawer', d.label, d.count, d.note || '',
                d.boxes.map(boxHtml).join(''), false)).join(''), false)).join(''), true)).join('')
        + `<div class="inv-total">${inv.total.toLocaleString()} tubes in the research section</div>`;

    // Open a box when its label is clicked, without toggling the fold.
    const setAll = (open) => body.querySelectorAll('details').forEach((d) => { d.open = open; });
    document.getElementById('btn-inv-expand').addEventListener('click', () => setAll(true));
    document.getElementById('btn-inv-collapse').addEventListener('click', () => setAll(false));
}
