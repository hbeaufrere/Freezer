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
    document.getElementById('retrieval-tube-ids').value = '';
    document.getElementById('retrieval-tube-heading').textContent = 'Tube';
    document.getElementById('retrieval-tube-label').textContent = label || '';
    document.getElementById('retrieval-help').textContent =
        'Logging a retrieval also counts one freeze-thaw cycle for this tube.';
    document.getElementById('retrieval-purpose').value = '';
    document.getElementById('retrieval-notes').value = '';
    document.getElementById('retrieval-consumed').checked = false;

    // Same person usually logs several in a row, so remember the name.
    let who = '';
    try { who = localStorage.getItem(RETRIEVER_KEY) || ''; } catch (e) { /* private mode */ }
    document.getElementById('retrieval-by').value = who;

    bootstrap.Modal.getOrCreateInstance(document.getElementById('retrievalModal')).show();
}

/* The same sheet for a group: one name, one purpose, one outcome, applied
   to every tube ticked. Twenty tubes for one assay are one trip to the
   freezer and should be one entry's worth of typing. */
function openRetrievalModalBulk(section, tubeIds, labels) {
    if (!tubeIds.length) return;

    document.getElementById('retrieval-section').value = section;
    document.getElementById('retrieval-tube-id').value = '';
    document.getElementById('retrieval-tube-ids').value = JSON.stringify(tubeIds);
    document.getElementById('retrieval-tube-heading').textContent =
        `${tubeIds.length} tube${tubeIds.length === 1 ? '' : 's'}`;
    const shown = labels.slice(0, 6).join(', ');
    document.getElementById('retrieval-tube-label').textContent =
        labels.length > 6 ? `${shown}, +${labels.length - 6} more` : shown;
    document.getElementById('retrieval-help').textContent =
        'Every tube here gets its own log entry and one freeze-thaw cycle.';
    document.getElementById('retrieval-purpose').value = '';
    document.getElementById('retrieval-notes').value = '';
    document.getElementById('retrieval-consumed').checked = false;

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

    const groupRaw = document.getElementById('retrieval-tube-ids').value;
    const group = groupRaw ? JSON.parse(groupRaw) : null;
    const payload = {
        section: document.getElementById('retrieval-section').value,
        retrieved_by: who,
        purpose: document.getElementById('retrieval-purpose').value.trim(),
        notes: document.getElementById('retrieval-notes').value.trim(),
        consumed: document.getElementById('retrieval-consumed').checked,
    };
    if (group) payload.tube_ids = group;
    else payload.tube_id = parseInt(document.getElementById('retrieval-tube-id').value, 10);

    const button = document.getElementById('btn-retrieval-save');
    button.disabled = true;
    try {
        const result = await API.post(group ? '/api/retrievals/bulk' : '/api/retrievals', payload);
        try { localStorage.setItem(RETRIEVER_KEY, who); } catch (e) { /* private mode */ }

        if (group) {
            showToast(result.removed
                ? `${result.logged} retrievals logged — ${result.removed} tubes removed from the freezer`
                : `${result.logged} retrievals logged — each tube gains one freeze-thaw cycle`);
        } else {
            showToast(result.tube_removed
                ? `Retrieval logged — ${result.tube_label} removed from the freezer`
                : `Retrieval logged — freeze-thaw now ${result.freeze_thaw_cycles}`);
        }

        bootstrap.Modal.getInstance(document.getElementById('retrievalModal')).hide();

        // The page that opened this sheet still shows the tubes as they were
        // before. Tell it what happened so it can catch up.
        document.dispatchEvent(new CustomEvent('retrievallogged', {
            detail: group ? {
                section: payload.section,
                tubeIds: group,
                bulk: true,
                tubeRemoved: Boolean(result.removed),
            } : {
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

/* ---- Shared with the activity page ------------------------ */

function formatWhen(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
    });
}
