/* A CBC reference-interval study: the table, the statistics the server
   recomputes from it, the three ways a CBC comes in, and the Excel sheet in
   the study's own folder that is rewritten after every change. */

const SLUG = document.getElementById('study-root').dataset.slug;
let STUDY = null;           // { study, rows, stats, n }
let cbcDraft = null;        // the parsed CBC being checked, when it came from VMACS or a paste
let importerReady = false;  // the Tampermonkey script has announced itself on this page

/* ---- numbers ---------------------------------------------- */

function fmt(x) {
    if (x === null || x === undefined) return '—';
    if (typeof x !== 'number') return escapeHtml(String(x));
    const a = Math.abs(x);
    const dp = a >= 100 ? 0 : a >= 10 ? 1 : 2;
    return Number(x.toFixed(dp)).toLocaleString(undefined, { maximumFractionDigits: dp });
}
const pair = (p) => (p ? `${fmt(p[0])} – ${fmt(p[1])}` : '—');

/* ---- load and render -------------------------------------- */

async function loadStudy() {
    STUDY = await API.get(`/api/studies/${encodeURIComponent(SLUG)}`);
    document.getElementById('study-n').textContent = STUDY.n;
    document.getElementById('study-prelim').hidden = !(STUDY.n > 0 && STUDY.preliminary);
    renderStats();
    renderData();
}

function renderStats() {
    const host = document.getElementById('study-stats');
    const stats = STUDY.stats.filter((s) => s.n > 0);
    if (!stats.length) {
        host.innerHTML = `<div class="empty-state border-0"><i class="bi bi-clipboard-data empty-icon"></i>
            <div class="empty-title">No CBCs yet</div>
            <div class="empty-hint">Import the first one and the intervals appear here.</div></div>`;
        return;
    }
    host.innerHTML = `
        <table class="table table-sm align-middle mb-0 study-table">
            <thead><tr>
                <th>Analyte</th><th class="num">n</th><th class="num">Mean</th><th class="num">SD</th>
                <th class="num">Median</th><th class="num">Min</th><th class="num">Max</th>
                <th class="num">95% RI</th><th class="num">90% CI, lower limit</th><th class="num">90% CI, upper limit</th>
                <th>Dixon outliers</th>
            </tr></thead>
            <tbody>${stats.map((s) => `
                <tr>
                    <td class="study-analyte">${escapeHtml(s.label)}${s.unit ? ` <span class="study-unit">${escapeHtml(s.unit)}</span>` : ''}</td>
                    <td class="num">${s.n}</td>
                    <td class="num">${fmt(s.mean)}</td><td class="num">${fmt(s.sd)}</td>
                    <td class="num">${fmt(s.median)}</td><td class="num">${fmt(s.min)}</td><td class="num">${fmt(s.max)}</td>
                    <td class="num study-ri">${fmt(s.ri_low)} – ${fmt(s.ri_high)}</td>
                    <td class="num">${pair(s.ci_low)}</td><td class="num">${pair(s.ci_high)}</td>
                    <td>${(s.outliers || []).map((o) => `<span class="study-outlier" title="${o.side === 'low' ? 'Lowest' : 'Highest'} value; its gap to the next exceeds a third of the range">${fmt(o.value)}${o.tag && o.tag.patient_no ? ` <span class="study-unit">#${escapeHtml(o.tag.patient_no)}</span>` : ''}</span>`).join(' ') || '<span class="text-body-secondary">none</span>'}</td>
                </tr>`).join('')}
            </tbody>
        </table>`;
}

function renderData() {
    const host = document.getElementById('study-data');
    const analytes = STUDY.study.analytes;
    if (!STUDY.rows.length) { host.innerHTML = '<div class="p-3 text-body-secondary small">Nothing in the table yet.</div>'; return; }
    const flagged = new Set();
    STUDY.stats.forEach((s) => (s.outliers || []).forEach((o) => flagged.add(`${o.tag && o.tag.row_id}|${s.key}`)));
    host.innerHTML = `
        <table class="table table-sm align-middle mb-0 study-table study-data">
            <thead><tr>
                <th class="sticky-col">Patient</th><th>WRMD</th><th>Collected</th><th>Age</th><th>Sex</th>
                ${analytes.map((a) => `<th class="num" title="${escapeHtml(a.key)}">${escapeHtml(a.label)}</th>`).join('')}
                <th></th>
            </tr></thead>
            <tbody>${STUDY.rows.map((r) => `
                <tr data-id="${r.id}">
                    <td class="sticky-col filter-tube">${escapeHtml(r.patient_no || '—')}</td>
                    <td>${escapeHtml(r.wrmd_number || '')}</td>
                    <td>${escapeHtml(r.collected_on || '')}</td>
                    <td>${escapeHtml(r.age || '')}</td>
                    <td>${escapeHtml(r.sex)}</td>
                    ${analytes.map((a) => {
                        const v = r.results[a.key];
                        const out = flagged.has(`${r.id}|${a.key}`);
                        return `<td class="num${out ? ' is-outlier' : ''}"${out ? ' title="Flagged by Dixon; retained"' : ''}>${v === undefined || v === null ? '' : fmt(v)}</td>`;
                    }).join('')}
                    <td class="text-end text-nowrap">
                        <button type="button" class="btn btn-sm btn-outline-secondary border-0" data-edit="${r.id}" title="Edit"><i class="bi bi-pencil"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-danger border-0" data-del="${r.id}" title="Remove from the study"><i class="bi bi-trash"></i></button>
                    </td>
                </tr>`).join('')}
            </tbody>
        </table>`;
    host.querySelectorAll('[data-edit]').forEach((b) => b.addEventListener('click', () =>
        openCbcModal({ row: STUDY.rows.find((r) => r.id === Number(b.dataset.edit)) })));
    host.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => removeCbc(Number(b.dataset.del))));
}

/* ---- the CBC sheet: check, then save ---------------------- */

let modalAnalytes = [];   // [{key,label,unit}] shown in the sheet

function setValueInputs(results) {
    document.getElementById('cbc-values').innerHTML = modalAnalytes.map((a) => {
        const v = results ? results[a.key] : undefined;
        return `<label class="cbc-value">
            <span>${escapeHtml(a.label)}${a.unit ? ` <span class="study-unit">${escapeHtml(a.unit)}</span>` : ''}</span>
            <input type="text" class="form-control form-control-sm" data-key="${escapeHtml(a.key)}" inputmode="decimal"
                   value="${v === undefined || v === null ? '' : escapeHtml(String(v))}">
        </label>`;
    }).join('') || '<div class="text-body-secondary small">No analytes yet. Add the first below.</div>';
}

function openCbcModal({ row = null, draft = null, prefill = {} } = {}) {
    cbcDraft = draft;
    const known = STUDY.study.analytes.slice();
    const seen = new Set(known.map((a) => a.key));
    (draft ? draft.analytes : []).forEach((a) => { if (!seen.has(a.key)) { seen.add(a.key); known.push(a); } });
    modalAnalytes = known;

    document.getElementById('cbc-id').value = row ? row.id : '';
    document.getElementById('cbc-title').textContent = row ? `Edit CBC — patient ${row.patient_no || '?'}` : 'Add a CBC';
    const note = document.getElementById('cbc-note');
    note.hidden = !(draft && draft.species_mismatch);
    if (draft && draft.species_mismatch) {
        note.innerHTML = `<i class="bi bi-exclamation-triangle me-1"></i>VMACS lists this bird as <strong>${escapeHtml(draft.breed || '')}</strong>, which is not this study's species. Check before saving.`;
    }

    const src = row || prefill;
    const panels = draft ? draft.panels : [];
    const start = draft && draft.default_panel !== null && draft.default_panel !== undefined ? draft.default_panel : 0;
    const wrap = document.getElementById('cbc-panel-wrap');
    const select = document.getElementById('cbc-panel');
    wrap.hidden = panels.length < 2;
    select.innerHTML = panels.map((p, i) => `<option value="${i}">${escapeHtml(p.label)}${i === start ? ' (latest)' : ''}</option>`).join('');
    select.value = String(start);

    const usePanel = (i) => {
        const p = panels[i];
        if (!p) return;
        document.getElementById('cbc-visit').value = p.visit_no || '';
        document.getElementById('cbc-date').value = p.collected_on || '';
        setValueInputs(p.results);
    };
    select.onchange = () => usePanel(Number(select.value));

    document.getElementById('cbc-patient').value = (draft && draft.patient_no) || src.patient_no || '';
    document.getElementById('cbc-wrmd').value = (draft && draft.wrmd_number) || src.wrmd_number || '';
    document.getElementById('cbc-visit').value = src.visit_no || '';
    document.getElementById('cbc-date').value = src.collected_on || '';
    document.getElementById('cbc-age').value = (draft && draft.age) || src.age || '';
    document.getElementById('cbc-sex').value = (draft && draft.sex) || src.sex || 'Unknown';
    document.getElementById('cbc-notes').value = src.notes || '';
    document.getElementById('cbc-new-name').value = '';
    if (panels.length) usePanel(start); else setValueInputs(row ? row.results : null);

    bootstrap.Modal.getOrCreateInstance(document.getElementById('cbcModal')).show();
}

function collectCbc() {
    const results = {};
    document.querySelectorAll('#cbc-values input[data-key]').forEach((el) => {
        const raw = el.value.trim();
        if (raw === '') return;
        const num = Number(raw.replace(',', ''));
        results[el.dataset.key] = Number.isFinite(num) && /^-?[\d.,]+$/.test(raw) ? num : raw;
    });
    return {
        patient_no: document.getElementById('cbc-patient').value.trim(),
        wrmd_number: document.getElementById('cbc-wrmd').value.trim(),
        visit_no: document.getElementById('cbc-visit').value.trim(),
        collected_on: document.getElementById('cbc-date').value || null,
        age: document.getElementById('cbc-age').value.trim(),
        sex: document.getElementById('cbc-sex').value,
        notes: document.getElementById('cbc-notes').value.trim(),
        results,
        analytes: modalAnalytes,
        source: cbcDraft ? cbcDraft.source : 'manual',
    };
}

async function sendCbc(url, method, payload) {
    const headers = { 'Content-Type': 'application/json' };
    try { const who = (localStorage.getItem('freezer-retrieved-by') || '').trim(); if (who) headers['X-Freezer-User'] = who; } catch (e) { /* private mode */ }
    const res = await fetch(url, { method, headers, body: JSON.stringify(payload) });
    const body = await res.json().catch(() => ({}));
    return { status: res.status, ok: res.ok, body };
}

async function saveCbc() {
    const id = document.getElementById('cbc-id').value;
    const payload = collectCbc();
    if (!Object.values(payload.results).some((v) => typeof v === 'number')) {
        showToast('There are no numeric results to save.', 'error');
        return;
    }
    const button = document.getElementById('btn-cbc-save');
    button.disabled = true;
    try {
        let r = id ? await sendCbc(`/api/study-cbcs/${id}`, 'PUT', payload)
                   : await sendCbc(`/api/studies/${encodeURIComponent(SLUG)}/cbcs`, 'POST', payload);
        if (r.status === 409 && r.body.duplicate) {
            if (!confirm(`${r.body.error}\n\nReplace the CBC already in the study with this one?`)) return;
            r = await sendCbc(`/api/studies/${encodeURIComponent(SLUG)}/cbcs`, 'POST', { ...payload, replace: true });
        }
        if (!r.ok) throw new Error(r.body.error || 'Could not save');
        bootstrap.Modal.getInstance(document.getElementById('cbcModal')).hide();
        showToast(id ? 'CBC updated' : (r.body.replaced ? 'CBC replaced' : 'CBC added to the study'));
        await loadStudy();
        syncExcel(true);     // the click on Save is the permission the browser needs
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        button.disabled = false;
    }
}

async function removeCbc(id) {
    const row = STUDY.rows.find((r) => r.id === id);
    if (!confirm(`Remove patient ${row.patient_no || '?'} from this study?\n\nIts values leave the table and the intervals are recomputed.`)) return;
    try {
        await API.del(`/api/study-cbcs/${id}`);
        showToast('Removed from the study');
        await loadStudy();
        syncExcel(true);
    } catch (err) { showToast(err.message, 'error'); }
}

/* ---- ways in ---------------------------------------------- */

/* Patient numbers in an email: 95-35-12, or six digits near a word that
   says what they are, or any six digits as a last resort. WRMD numbers look
   like 26-1042 and are kept for the row. */
function findIds(textIn) {
    const t = textIn || '';
    const patients = [];
    const add = (v) => { const d = v.replace(/\D/g, ''); if (d.length === 6 && !patients.includes(d)) patients.push(d); };
    (t.match(/\b\d{2}-\d{2}-\d{2}\b/g) || []).forEach(add);
    (t.match(/(?:vmth|vmacs|patient|case|pt)\s*(?:#|no\.?|number|id)?\s*[:#]?\s*(\d{6})\b/gi) || []).forEach(add);
    (t.match(/\b\d{6}\b/g) || []).forEach(add);
    const wrmd = (t.match(/\b\d{2}-\d{3,5}\b/g) || []).filter((w) => !/^\d{2}-\d{2}-\d{2}$/.test(w));
    return { patients, wrmd };
}

async function importFromEmail() {
    let copied = '';
    try { copied = await navigator.clipboard.readText(); } catch (e) { /* no permission: ask */ }
    if (!copied.trim()) copied = prompt('Paste the email here:') || '';
    const ids = findIds(copied);
    if (!ids.patients.length) {
        showToast('No six-digit VMACS patient number in what was copied.', 'error');
        return;
    }
    let patient = ids.patients[0];
    if (ids.patients.length > 1) {
        const pick = prompt(`Several numbers look like patient numbers:\n${ids.patients.join(', ')}\n\nWhich one?`, patient);
        if (!pick) return;
        patient = pick.replace(/\D/g, '');
    }
    const wrmd = ids.wrmd[0] || '';
    if (importerReady) {
        window.postMessage({ type: 'ri-open-vmacs', patient, study: SLUG, wrmd }, window.location.origin);
        showToast(`Opening VMACS for patient ${patient}…`);
    } else {
        showToast('The VMACS importer is not installed in this browser, so the values need pasting or typing.', 'warning');
        openCbcModal({ prefill: { patient_no: patient, wrmd_number: wrmd } });
    }
}

async function readPasted() {
    const textIn = document.getElementById('paste-text').value;
    try {
        const parsed = await API.post('/api/studies/parse', { kind: 'text', text: textIn, study: SLUG });
        bootstrap.Modal.getInstance(document.getElementById('pasteModal')).hide();
        openCbcModal({ draft: parsed });
    } catch (err) { showToast(err.message, 'error'); }
}

/* ---- the Excel sheet in the study's folder ---------------- */

/* A website cannot write to a disk on its own. Chrome and Edge can, once
   the person has picked the file: the handle is kept in the browser's own
   database, and from then on the sheet is rewritten after every change.
   Elsewhere (Safari, Firefox, phones) the Download button is the fallback. */
const CAN_LINK = 'showSaveFilePicker' in window;

function idb() {
    return new Promise((resolve, reject) => {
        const open = indexedDB.open('freezer-studies', 1);
        open.onupgradeneeded = () => open.result.createObjectStore('handles');
        open.onsuccess = () => resolve(open.result);
        open.onerror = () => reject(open.error);
    });
}
async function idbGet(key) {
    const db = await idb();
    return new Promise((resolve, reject) => {
        const r = db.transaction('handles').objectStore('handles').get(key);
        r.onsuccess = () => resolve(r.result || null); r.onerror = () => reject(r.error);
    });
}
async function idbSet(key, value) {
    const db = await idb();
    return new Promise((resolve, reject) => {
        const tx = db.transaction('handles', 'readwrite');
        tx.objectStore('handles').put(value, key);
        tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error);
    });
}

function excelState(textIn, cls = '') {
    const el = document.getElementById('excel-state');
    el.textContent = textIn; el.className = `study-excel-state ${cls}`;
}

async function refreshExcelUi() {
    const link = document.getElementById('btn-excel-link');
    if (!CAN_LINK) {
        link.hidden = true;
        excelState('This browser cannot write to a folder. Use Download, or open the study in Chrome on the computer.');
        return;
    }
    const handle = await idbGet(SLUG).catch(() => null);
    document.getElementById('btn-excel-sync').hidden = !handle;
    document.getElementById('excel-link-label').textContent = handle ? 'Change file' : 'Link the file in the study folder';
    if (handle) excelState(`Linked: ${handle.name}`, 'is-linked');
}

async function linkExcel() {
    try {
        const handle = await window.showSaveFilePicker({
            suggestedName: `${STUDY.study.name} - CBC data.xlsx`,
            types: [{ description: 'Excel workbook', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }],
        });
        await idbSet(SLUG, handle);
        await refreshExcelUi();
        await syncExcel(true);
    } catch (err) {
        if (err.name !== 'AbortError') showToast(err.message, 'error');
    }
}

/* Rewrite the linked sheet. fromClick says a person just clicked, which is
   when the browser will let us ask for permission again. */
async function syncExcel(fromClick) {
    if (!CAN_LINK) return;
    const handle = await idbGet(SLUG).catch(() => null);
    if (!handle) return;
    try {
        let perm = await handle.queryPermission({ mode: 'readwrite' });
        if (perm !== 'granted' && fromClick) perm = await handle.requestPermission({ mode: 'readwrite' });
        if (perm !== 'granted') {
            excelState(`${handle.name} is waiting: press Update now`, 'is-stale');
            return;
        }
        const res = await fetch(`/api/studies/${encodeURIComponent(SLUG)}/xlsx`);
        if (!res.ok) throw new Error('Could not build the sheet');
        const writable = await handle.createWritable();
        await writable.write(await res.blob());
        await writable.close();
        excelState(`${handle.name} updated ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`, 'is-linked');
    } catch (err) {
        excelState(`${handle.name} was not updated`, 'is-stale');
        showToast(err.name === 'NoModificationAllowedError' || /locked|in use/i.test(err.message)
            ? 'The Excel file is open. Close it and press Update now.'
            : `Excel sheet not updated: ${err.message}`, 'error');
    }
}

/* ---- wiring ----------------------------------------------- */

window.addEventListener('message', (event) => {
    if (event.origin !== window.location.origin || !event.data) return;
    if (event.data.type === 'ri-userscript-ready') {
        importerReady = true;
        document.getElementById('study-importer-state').innerHTML = '<i class="bi bi-check-circle me-1"></i>VMACS importer installed';
    }
    if (event.data.type === 'ri-need-vmacs') {
        showToast('Open VMACS once in this browser so the importer learns its address, then try again.', 'warning');
    }
});

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('btn-study-email').addEventListener('click', importFromEmail);
    document.getElementById('btn-study-paste').addEventListener('click', () => {
        document.getElementById('paste-text').value = '';
        bootstrap.Modal.getOrCreateInstance(document.getElementById('pasteModal')).show();
    });
    document.getElementById('btn-study-manual').addEventListener('click', () => openCbcModal());
    document.getElementById('btn-paste-read').addEventListener('click', readPasted);
    document.getElementById('btn-cbc-save').addEventListener('click', saveCbc);
    document.getElementById('btn-cbc-new').addEventListener('click', () => {
        const name = document.getElementById('cbc-new-name').value.trim();
        if (!name) return;
        const key = name.replace(/^CBC[_\s:-]*/i, '').replace(/[^A-Za-z0-9%#]+/g, '_').replace(/^_+|_+$/g, '').toUpperCase().slice(0, 40);
        if (!key || modalAnalytes.some((a) => a.key === key)) return;
        const current = collectCbc().results;
        modalAnalytes = modalAnalytes.concat([{ key, label: name.slice(0, 60), unit: '' }]);
        setValueInputs(current);
        document.getElementById('cbc-new-name').value = '';
        document.querySelector(`#cbc-values input[data-key="${key}"]`)?.focus();
    });
    document.getElementById('btn-excel-link').addEventListener('click', linkExcel);
    document.getElementById('btn-excel-sync').addEventListener('click', () => syncExcel(true));
    window.postMessage({ type: 'ri-study-page-ready' }, window.location.origin);

    try {
        await loadStudy();
    } catch (err) { showToast(err.message, 'error'); return; }
    await refreshExcelUi();
    syncExcel(false);

    // A CBC handed over by the VMACS importer, waiting to be checked.
    const pending = sessionStorage.getItem('ri-pending-import');
    if (pending) {
        sessionStorage.removeItem('ri-pending-import');
        try { openCbcModal({ draft: JSON.parse(pending) }); } catch (e) { /* stale */ }
    }
});
