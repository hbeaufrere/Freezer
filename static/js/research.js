/* Research section page logic */

let currentResearchBoxId = null;
let currentResearchBoxData = null;

async function initResearchPage() {
    // Expose box click for refreshFreezerView
    window._onResearchBoxClick = onResearchBoxClick;

    // Load sidebar racks
    await renderSectionSidebar('research-rack-sidebar', 'research', onResearchBoxClick);

    // Load quick stats
    loadResearchQuickStats();

    // Check URL for pre-selected box
    const params = new URLSearchParams(window.location.search);
    const boxId = params.get('box');
    if (boxId) onResearchBoxClick(parseInt(boxId));

    // Search functionality
    const searchInput = document.getElementById('research-search');
    searchInput.addEventListener('input', debounce(onResearchSearch, 300));
    searchInput.addEventListener('blur', () => {
        setTimeout(() => {
            document.getElementById('research-search-results').classList.remove('show');
        }, 200);
    });

    // Modal buttons
    document.getElementById('btn-research-save').addEventListener('click', saveResearchTube);
    document.getElementById('btn-research-delete').addEventListener('click', deleteResearchTube);
    document.getElementById('btn-research-thaw').addEventListener('click', recordResearchThaw);
}

async function loadResearchQuickStats() {
    try {
        const stats = await API.get('/api/stats/research');
        document.getElementById('research-stat-total').textContent = `${stats.total_samples} tubes`;
        document.getElementById('research-stat-boxes').textContent = `${stats.boxes_with_samples} boxes in use`;
    } catch (err) {
        console.error('Failed to load research stats:', err);
    }
}

async function onResearchBoxClick(boxId, boxInfo) {
    currentResearchBoxId = boxId;

    // Highlight selected box
    document.querySelectorAll('#research-rack-sidebar .box-slot').forEach(el => el.classList.remove('selected'));
    const selectedEl = document.querySelector(`#research-rack-sidebar .box-slot[data-box-id="${boxId}"]`);
    if (selectedEl) selectedEl.classList.add('selected');

    try {
        const boxData = await API.get(`/api/boxes/${boxId}`);
        currentResearchBoxData = boxData;

        // Update breadcrumb
        document.getElementById('research-breadcrumb').innerHTML =
            `<span onclick="window.location.href='/research'">${boxData.shelf_name}</span> &rsaquo; ` +
            `${boxData.rack_label} &rsaquo; ${boxData.drawer_label} &rsaquo; <strong>${boxData.label}</strong>`;

        // Render grid
        renderBoxGrid(document.getElementById('research-grid-area'), boxData, {
            onTubeClick: openResearchEditModal,
            onEmptyClick: openResearchAddModal,
        });
    } catch (err) {
        showToast('Failed to load box: ' + err.message, 'error');
    }
}

function openResearchAddModal(row, col) {
    document.getElementById('researchTubeModalTitle').textContent = 'Add Research Tube';
    document.getElementById('research-tube-id').value = '';
    document.getElementById('research-tube-box-id').value = currentResearchBoxId;
    document.getElementById('research-tube-row').value = row;
    document.getElementById('research-tube-col').value = col;
    document.getElementById('research-tube-position').textContent =
        `${currentResearchBoxData.label} — Position ${positionLabel(row, col)}`;
    document.getElementById('research-sample-id').value = '';
    document.getElementById('research-description').value = '';
    document.getElementById('research-date-stored').value = new Date().toISOString().split('T')[0];
    document.getElementById('research-freeze-thaw').value = 0;
    document.getElementById('btn-research-delete').style.display = 'none';
    document.getElementById('btn-research-thaw').style.display = 'none';

    new bootstrap.Modal(document.getElementById('researchTubeModal')).show();
}

function openResearchEditModal(tube, row, col) {
    document.getElementById('researchTubeModalTitle').textContent = 'Edit Research Tube';
    document.getElementById('research-tube-id').value = tube.id;
    document.getElementById('research-tube-box-id').value = tube.box_id;
    document.getElementById('research-tube-row').value = row;
    document.getElementById('research-tube-col').value = col;
    document.getElementById('research-tube-position').textContent =
        `${currentResearchBoxData.label} — Position ${positionLabel(row, col)}`;
    document.getElementById('research-sample-id').value = tube.sample_id || '';
    document.getElementById('research-description').value = tube.description || '';
    document.getElementById('research-date-stored').value = tube.date_stored || '';
    document.getElementById('research-freeze-thaw').value = tube.freeze_thaw_cycles || 0;
    document.getElementById('btn-research-delete').style.display = 'inline-block';
    document.getElementById('btn-research-thaw').style.display = 'inline-block';

    new bootstrap.Modal(document.getElementById('researchTubeModal')).show();
}

async function saveResearchTube() {
    const tubeId = document.getElementById('research-tube-id').value;
    const data = {
        box_id: parseInt(document.getElementById('research-tube-box-id').value),
        row_pos: parseInt(document.getElementById('research-tube-row').value),
        col_pos: parseInt(document.getElementById('research-tube-col').value),
        sample_id: document.getElementById('research-sample-id').value.trim(),
        description: document.getElementById('research-description').value.trim(),
        date_stored: document.getElementById('research-date-stored').value || null,
        freeze_thaw_cycles: parseInt(document.getElementById('research-freeze-thaw').value) || 0,
    };

    try {
        if (tubeId) {
            await API.put(`/api/research/tubes/${tubeId}`, data);
            showToast('Tube updated successfully');
        } else {
            await API.post('/api/research/tubes', data);
            showToast('Tube added successfully');
        }
        bootstrap.Modal.getInstance(document.getElementById('researchTubeModal')).hide();
        onResearchBoxClick(currentResearchBoxId);
        loadResearchQuickStats();
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

function recordResearchThaw() {
    const tubeId = document.getElementById('research-tube-id').value;
    if (!tubeId) return;

    const sampleId = document.getElementById('research-sample-id').value || `#${tubeId}`;

    // Close the tube modal first, then show retrieval prompt
    const tubeModal = bootstrap.Modal.getInstance(document.getElementById('researchTubeModal'));
    if (tubeModal) tubeModal.hide();

    showRetrievalPrompt(
        'Record Freeze-Thaw',
        `Recording a freeze-thaw cycle for sample "${sampleId}". Please log who is retrieving it and for what purpose.`,
        async ({ retrieved_by, purpose }) => {
            try {
                const result = await API.put(`/api/research/tubes/${tubeId}/thaw`, { retrieved_by, purpose });
                showToast(`Freeze-thaw cycle recorded (now ${result.freeze_thaw_cycles})`);
                onResearchBoxClick(currentResearchBoxId);
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        }
    );
}

function deleteResearchTube() {
    const tubeId = document.getElementById('research-tube-id').value;
    if (!tubeId) return;

    const sampleId = document.getElementById('research-sample-id').value || `#${tubeId}`;

    // Close the tube modal first, then show retrieval prompt
    const tubeModal = bootstrap.Modal.getInstance(document.getElementById('researchTubeModal'));
    if (tubeModal) tubeModal.hide();

    showRetrievalPrompt(
        'Remove Sample',
        `Removing sample "${sampleId}" from the freezer. Please log who is removing it and for what purpose.`,
        async ({ retrieved_by, purpose }) => {
            try {
                await API.del(`/api/research/tubes/${tubeId}`, { retrieved_by, purpose });
                showToast('Tube removed');
                onResearchBoxClick(currentResearchBoxId);
                loadResearchQuickStats();
            } catch (err) {
                showToast('Error: ' + err.message, 'error');
            }
        }
    );
}

async function onResearchSearch() {
    const q = document.getElementById('research-search').value.trim();
    const dropdown = document.getElementById('research-search-results');
    if (!q) {
        dropdown.classList.remove('show');
        return;
    }
    try {
        const results = await API.get(`/api/research/search?q=${encodeURIComponent(q)}`);
        if (results.length === 0) {
            dropdown.innerHTML = '<div class="search-result-item text-muted">No results found</div>';
        } else {
            dropdown.innerHTML = results.map(r => `
                <div class="search-result-item" onclick="onResearchBoxClick(${r.box_id})">
                    <strong>${r.sample_id || 'No ID'}</strong>
                    <span class="text-muted ms-2">${r.rack_label} / ${r.box_label} / ${positionLabel(r.row_pos, r.col_pos)}</span>
                    ${r.description ? `<br><small class="text-muted">${r.description}</small>` : ''}
                </div>
            `).join('');
        }
        dropdown.classList.add('show');
    } catch (err) {
        console.error('Search failed:', err);
    }
}
