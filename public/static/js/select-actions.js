/* Tick boxes on a filter's rows, then act on the lot: log one retrieval
   for all of them, or count a freeze-thaw cycle on each. Shared by the
   raptor and research filters on the statistics page.

   Selection survives a re-render of the table (the filter re-runs after
   every action), but not a change of criteria: a new list is a new set. */

function makeSelection({ section, prefix, tableHost, onDone }) {
    const chosen = new Map();   // tube id -> label
    const bar = document.getElementById(`${prefix}-select-bar`);
    const countEl = document.getElementById(`${prefix}-selected-n`);

    function refreshBar() {
        countEl.textContent = chosen.size;
        bar.hidden = chosen.size === 0;
    }

    function clear() {
        chosen.clear();
        tableHost.querySelectorAll('input.pick').forEach((cb) => { cb.checked = false; });
        const all = tableHost.querySelector('input.pick-all');
        if (all) all.checked = false;
        refreshBar();
    }

    /* Wire the checkboxes a freshly rendered table contains. Rows carry
       data-tube-id and data-label; rows without an id (whole boxes) get no
       box and cannot be ticked. */
    function wire() {
        const picks = [...tableHost.querySelectorAll('input.pick')];
        picks.forEach((cb) => {
            cb.checked = chosen.has(Number(cb.dataset.tubeId));
            cb.addEventListener('change', () => {
                const id = Number(cb.dataset.tubeId);
                if (cb.checked) chosen.set(id, cb.dataset.label);
                else chosen.delete(id);
                syncAll();
                refreshBar();
            });
        });
        const all = tableHost.querySelector('input.pick-all');
        function syncAll() {
            if (!all) return;
            const ticked = picks.filter((cb) => cb.checked).length;
            all.checked = picks.length > 0 && ticked === picks.length;
            all.indeterminate = ticked > 0 && ticked < picks.length;
        }
        if (all) {
            all.addEventListener('change', () => {
                picks.forEach((cb) => {
                    cb.checked = all.checked;
                    const id = Number(cb.dataset.tubeId);
                    if (all.checked) chosen.set(id, cb.dataset.label);
                    else chosen.delete(id);
                });
                syncAll();
                refreshBar();
            });
        }
        // Drop anything no longer in the list (it was consumed, or the
        // criteria changed), so the count never claims tubes it cannot act on.
        const present = new Set(picks.map((cb) => Number(cb.dataset.tubeId)));
        [...chosen.keys()].forEach((id) => { if (!present.has(id)) chosen.delete(id); });
        syncAll();
        refreshBar();
    }

    document.getElementById(`btn-${prefix}-unselect`).addEventListener('click', clear);

    document.getElementById(`btn-${prefix}-retrieve`).addEventListener('click', () => {
        openRetrievalModalBulk(section, [...chosen.keys()], [...chosen.values()]);
    });

    document.getElementById(`btn-${prefix}-thaw`).addEventListener('click', async () => {
        const n = chosen.size;
        if (!confirm(`Count one freeze-thaw cycle on ${n} tube${n === 1 ? '' : 's'}?\n\n`
            + 'This is for tubes that came out and went back without a retrieval being '
            + 'logged at the time. No log entry is written.')) return;
        try {
            const result = await API.post('/api/tubes/thaw', { section, tube_ids: [...chosen.keys()] });
            showToast(`Freeze-thaw cycle recorded on ${result.thawed} tube${result.thawed === 1 ? '' : 's'}`);
            clear();
            onDone();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    document.addEventListener('retrievallogged', (event) => {
        if (event.detail?.bulk && event.detail.section === section) {
            clear();
            onDone();
        }
    });

    return { wire, clear, get size() { return chosen.size; } };
}

/* The header cell and the row cell the tables render. */
function pickHeaderCell() {
    return '<th class="pick-col"><input type="checkbox" class="form-check-input pick-all" aria-label="Select all shown"></th>';
}

function pickCell(tubeId, label) {
    if (tubeId === null || tubeId === undefined) return '<td class="pick-col"></td>';
    return `<td class="pick-col"><input type="checkbox" class="form-check-input pick"
        data-tube-id="${tubeId}" data-label="${escapeHtml(label || '')}" aria-label="Select ${escapeHtml(label || 'sample')}"></td>`;
}
