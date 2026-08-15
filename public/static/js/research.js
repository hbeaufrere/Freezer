/* CLIPR research section page. */

let currentResearchBoxId = null;
let currentResearchBox = null;

async function initResearchPage() {
    await renderSectionSidebar('research-rack-sidebar', 'research', openResearchBox);
    loadResearchQuickStats();

    const preselected = new URLSearchParams(window.location.search).get('box');
    if (preselected) openResearchBox(parseInt(preselected, 10));

    const search = document.getElementById('research-search');
    const dropdown = document.getElementById('research-search-results');
    search.addEventListener('input', debounce(runResearchSearch, 250));
    search.addEventListener('blur', () => setTimeout(() => {
        dropdown.classList.remove('show');
        search.setAttribute('aria-expanded', 'false');
    }, 150));
    attachSearchKeys(search, dropdown);

    document.getElementById('btn-research-save').addEventListener('click', saveResearchTube);
    document.getElementById('btn-research-delete').addEventListener('click', deleteResearchTube);
    document.getElementById('btn-research-thaw').addEventListener('click', recordResearchThaw);
    document.getElementById('btn-research-barcode').addEventListener('click', showResearchBarcode);
}

async function loadResearchQuickStats() {
    try {
        const stats = await API.get('/api/stats/research');
        document.getElementById('research-stat-total').textContent = stats.total_samples;
        document.getElementById('research-stat-boxes').textContent = stats.boxes_with_samples;
    } catch (err) {
        console.error('Research stats failed to load:', err);
    }
}

async function openResearchBox(boxId) {
    currentResearchBoxId = boxId;

    document.querySelectorAll('#research-rack-sidebar .box-slot')
        .forEach((el) => el.classList.remove('selected'));
    document.querySelector(`#research-rack-sidebar .box-slot[data-box-id="${boxId}"]`)
        ?.classList.add('selected');

    try {
        const box = await API.get(`/api/boxes/${boxId}`);
        currentResearchBox = box;

        const crumb = document.getElementById('research-breadcrumb');
        crumb.textContent = '';
        crumb.innerHTML =
            `<button type="button" onclick="window.location.href='/research'">${escapeHtml(box.shelf_name)}</button>` +
            `<span>&rsaquo;</span><span>${escapeHtml(box.rack_label)}</span>` +
            `<span>&rsaquo;</span><span>${escapeHtml(box.drawer_label)}</span>` +
            `<span>&rsaquo;</span><strong>${escapeHtml(box.label)}</strong>`;

        renderBoxGrid(document.getElementById('research-grid-area'), box, {
            onTubeClick: openResearchEditModal,
            onEmptyClick: openResearchAddModal,
        });
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function setHidden(id, hidden) {
    document.getElementById(id).hidden = hidden;
}

function openResearchAddModal(row, col) {
    document.getElementById('researchTubeModalTitle').textContent = 'Add research tube';
    document.getElementById('research-tube-id').value = '';
    document.getElementById('research-tube-box-id').value = currentResearchBoxId;
    document.getElementById('research-tube-row').value = row;
    document.getElementById('research-tube-col').value = col;
    document.getElementById('research-tube-position').textContent =
        `${currentResearchBox.label} · ${positionLabel(row, col)}`;
    document.getElementById('research-sample-id').value = '';
    document.getElementById('research-description').value = '';
    document.getElementById('research-date-stored').value = today();
    document.getElementById('research-freeze-thaw').value = 0;
    setHidden('btn-research-delete', true);
    setHidden('btn-research-thaw', true);
    setHidden('btn-research-barcode', true);

    bootstrap.Modal.getOrCreateInstance(document.getElementById('researchTubeModal')).show();
}

function openResearchEditModal(tube, row, col) {
    document.getElementById('researchTubeModalTitle').textContent = 'Edit research tube';
    document.getElementById('research-tube-id').value = tube.id;
    document.getElementById('research-tube-box-id').value = tube.box_id;
    document.getElementById('research-tube-row').value = row;
    document.getElementById('research-tube-col').value = col;
    document.getElementById('research-tube-position').textContent =
        `${currentResearchBox.label} · ${positionLabel(row, col)}`;
    document.getElementById('research-sample-id').value = tube.sample_id || '';
    document.getElementById('research-description').value = tube.description || '';
    document.getElementById('research-date-stored').value = tube.date_stored || '';
    document.getElementById('research-freeze-thaw').value = tube.freeze_thaw_cycles || 0;
    setHidden('btn-research-delete', false);
    setHidden('btn-research-thaw', false);
    setHidden('btn-research-barcode', false);

    bootstrap.Modal.getOrCreateInstance(document.getElementById('researchTubeModal')).show();
}

function showResearchBarcode() {
    const sampleId = document.getElementById('research-sample-id').value.trim();
    showLabelBarcode(sampleId, currentResearchBox ? currentResearchBox.label : '');
}

async function saveResearchTube() {
    const tubeId = document.getElementById('research-tube-id').value;
    const payload = {
        box_id: parseInt(document.getElementById('research-tube-box-id').value, 10),
        row_pos: parseInt(document.getElementById('research-tube-row').value, 10),
        col_pos: parseInt(document.getElementById('research-tube-col').value, 10),
        sample_id: document.getElementById('research-sample-id').value.trim(),
        description: document.getElementById('research-description').value.trim(),
        date_stored: document.getElementById('research-date-stored').value || null,
        freeze_thaw_cycles: parseInt(document.getElementById('research-freeze-thaw').value, 10) || 0,
    };

    const button = document.getElementById('btn-research-save');
    button.disabled = true;
    try {
        if (tubeId) {
            await API.put(`/api/research/tubes/${tubeId}`, payload);
            showToast('Tube updated');
        } else {
            await API.post('/api/research/tubes', payload);
            showToast('Tube added');
        }
        bootstrap.Modal.getInstance(document.getElementById('researchTubeModal')).hide();
        await openResearchBox(currentResearchBoxId);
        loadResearchQuickStats();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        button.disabled = false;
    }
}

async function recordResearchThaw() {
    const tubeId = document.getElementById('research-tube-id').value;
    if (!tubeId) return;
    try {
        const tube = await API.put(`/api/research/tubes/${tubeId}/thaw`);
        document.getElementById('research-freeze-thaw').value = tube.freeze_thaw_cycles;
        showToast(`Freeze-thaw cycle recorded — now ${tube.freeze_thaw_cycles}`);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function deleteResearchTube() {
    const tubeId = document.getElementById('research-tube-id').value;
    if (!tubeId) return;

    const label = document.getElementById('research-sample-id').value.trim() || 'this tube';
    if (!confirm(`Remove ${label} from the freezer record? This cannot be undone.`)) return;

    try {
        await API.del(`/api/research/tubes/${tubeId}`);
        showToast('Tube removed');
        bootstrap.Modal.getInstance(document.getElementById('researchTubeModal')).hide();
        await openResearchBox(currentResearchBoxId);
        loadResearchQuickStats();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function runResearchSearch() {
    const input = document.getElementById('research-search');
    const dropdown = document.getElementById('research-search-results');
    const query = input.value.trim();

    if (!query) {
        dropdown.classList.remove('show');
        input.setAttribute('aria-expanded', 'false');
        return;
    }

    try {
        const results = await API.get(`/api/research/search?q=${encodeURIComponent(query)}`);
        dropdown.textContent = '';

        if (!results.length) {
            dropdown.innerHTML = '<div class="search-empty">No tubes match that search.</div>';
        } else {
            results.forEach((row) => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'search-result-item';
                item.dataset.selectable = 'true';
                item.setAttribute('role', 'option');
                item.innerHTML = `
                    <span class="result-id">${escapeHtml(row.sample_id || 'Untitled sample')}</span>
                    <div class="result-meta">
                        ${escapeHtml(row.rack_label)} · ${escapeHtml(row.box_label)} ·
                        ${positionLabel(row.row_pos, row.col_pos)}
                        ${row.description ? '— ' + escapeHtml(row.description.slice(0, 60)) : ''}
                    </div>`;
                item.addEventListener('click', () => {
                    dropdown.classList.remove('show');
                    openResearchBox(row.box_id);
                });
                dropdown.appendChild(item);
            });
        }

        dropdown.classList.add('show');
        input.setAttribute('aria-expanded', 'true');
    } catch (err) {
        console.error('Search failed:', err);
    }
}
