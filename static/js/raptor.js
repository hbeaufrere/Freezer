/* Raptor biobank page logic */

let currentRaptorBoxId = null;
let currentRaptorBoxData = null;
let speciesList = [];

async function initRaptorPage() {
    // Load species list first
    speciesList = await API.get('/api/species');
    populateSpeciesDropdown();

    // Load sidebar racks (upper shelf only)
    await renderSectionSidebar('raptor-rack-sidebar', 'raptor', onRaptorBoxClick);

    // Load quick stats
    loadRaptorQuickStats();

    // Check URL for pre-selected box
    const params = new URLSearchParams(window.location.search);
    const boxId = params.get('box');
    if (boxId) onRaptorBoxClick(parseInt(boxId));

    // Search
    const searchInput = document.getElementById('raptor-search');
    searchInput.addEventListener('input', debounce(onRaptorSearch, 300));
    searchInput.addEventListener('blur', () => {
        setTimeout(() => {
            document.getElementById('raptor-search-results').classList.remove('show');
        }, 200);
    });

    // Modal buttons
    document.getElementById('btn-raptor-save').addEventListener('click', saveRaptorTube);
    document.getElementById('btn-raptor-delete').addEventListener('click', deleteRaptorTube);
    document.getElementById('btn-raptor-thaw').addEventListener('click', recordThaw);
    document.getElementById('btn-raptor-print').addEventListener('click', printRaptorLabel);
    document.getElementById('btn-add-species').addEventListener('click', addNewSpecies);
}

function populateSpeciesDropdown() {
    const select = document.getElementById('raptor-species');
    // Keep first option
    select.innerHTML = '<option value="">-- Select Species --</option>';
    speciesList.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = `${s.banding_code} - ${s.common_name} (${s.scientific_name})`;
        select.appendChild(opt);
    });
    // Add "new species" option
    const addOpt = document.createElement('option');
    addOpt.value = '__new__';
    addOpt.textContent = '+ Add new species...';
    select.appendChild(addOpt);

    select.addEventListener('change', () => {
        if (select.value === '__new__') {
            select.value = '';
            new bootstrap.Modal(document.getElementById('addSpeciesModal')).show();
        }
    });
}

async function loadRaptorQuickStats() {
    try {
        const stats = await API.get('/api/stats/raptor');
        document.getElementById('raptor-stat-total').textContent = `${stats.total_samples} samples`;
        const speciesCount = stats.species_breakdown ? stats.species_breakdown.length : 0;
        document.getElementById('raptor-stat-species').textContent = `${speciesCount} species`;
    } catch (err) {
        console.error('Failed to load raptor stats:', err);
    }
}

async function onRaptorBoxClick(boxId, boxInfo) {
    currentRaptorBoxId = boxId;

    // Highlight selected box
    document.querySelectorAll('#raptor-rack-sidebar .box-slot').forEach(el => el.classList.remove('selected'));
    const selectedEl = document.querySelector(`#raptor-rack-sidebar .box-slot[data-box-id="${boxId}"]`);
    if (selectedEl) selectedEl.classList.add('selected');

    try {
        const boxData = await API.get(`/api/boxes/${boxId}`);
        currentRaptorBoxData = boxData;

        document.getElementById('raptor-breadcrumb').innerHTML =
            `<span onclick="window.location.href='/raptor'">${boxData.shelf_name}</span> &rsaquo; ` +
            `${boxData.rack_label} &rsaquo; ${boxData.drawer_label} &rsaquo; <strong>${boxData.label}</strong>`;

        const legendData = renderBoxGrid(document.getElementById('raptor-grid-area'), boxData, {
            onTubeClick: openRaptorEditModal,
            onEmptyClick: openRaptorAddModal,
        });

        // Update species legend
        if (legendData && Object.keys(legendData.speciesIndexMap).length > 0) {
            const legendItems = document.getElementById('raptor-legend-items');
            legendItems.innerHTML = '';
            for (const [code, idx] of Object.entries(legendData.speciesIndexMap)) {
                const species = speciesList.find(s => s.banding_code === code);
                const name = species ? species.common_name : code;
                legendItems.innerHTML += `
                    <span class="badge" style="background: var(--bs-body-bg); border: 1px solid #ccc;">
                        <span class="tube-cell species-${idx % 12}" style="display:inline-block;width:12px;height:12px;min-width:12px;min-height:12px;border-radius:50%;vertical-align:middle;"></span>
                        <small class="ms-1">${code} - ${name}</small>
                    </span>
                `;
            }
            document.getElementById('raptor-species-legend').style.display = 'block';
        } else {
            document.getElementById('raptor-species-legend').style.display = 'none';
        }
    } catch (err) {
        showToast('Failed to load box: ' + err.message, 'error');
    }
}

function openRaptorAddModal(row, col) {
    document.getElementById('raptorTubeModalTitle').textContent = 'Add Raptor Sample';
    document.getElementById('raptor-tube-db-id').value = '';
    document.getElementById('raptor-tube-box-id').value = currentRaptorBoxId;
    document.getElementById('raptor-tube-row').value = row;
    document.getElementById('raptor-tube-col').value = col;
    document.getElementById('raptor-tube-position').textContent =
        `${currentRaptorBoxData.label} — Position ${positionLabel(row, col)}`;
    document.getElementById('raptor-tube-id-display').style.display = 'none';
    document.getElementById('raptor-species').value = '';
    document.getElementById('raptor-collection-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('raptor-age').value = '';
    document.getElementById('raptor-sex-u').checked = true;
    document.getElementById('raptor-freeze-thaw').value = 0;
    document.getElementById('raptor-wrmd').value = '';
    document.getElementById('raptor-vmth').value = '';
    document.getElementById('raptor-notes').value = '';
    document.getElementById('raptor-species').disabled = false;
    document.getElementById('btn-raptor-delete').style.display = 'none';
    document.getElementById('btn-raptor-thaw').style.display = 'none';
    document.getElementById('btn-raptor-print').style.display = 'none';

    new bootstrap.Modal(document.getElementById('raptorTubeModal')).show();
}

function openRaptorEditModal(tube, row, col) {
    document.getElementById('raptorTubeModalTitle').textContent = 'Edit Raptor Sample';
    document.getElementById('raptor-tube-db-id').value = tube.id;
    document.getElementById('raptor-tube-box-id').value = tube.box_id;
    document.getElementById('raptor-tube-row').value = row;
    document.getElementById('raptor-tube-col').value = col;
    document.getElementById('raptor-tube-position').textContent =
        `${currentRaptorBoxData.label} — Position ${positionLabel(row, col)}`;

    // Show tube ID badge
    document.getElementById('raptor-tube-id-display').style.display = 'block';
    document.getElementById('raptor-tube-id-badge').textContent = tube.tube_id;

    document.getElementById('raptor-species').value = tube.species_id;
    document.getElementById('raptor-species').disabled = true; // Species immutable after creation
    document.getElementById('raptor-collection-date').value = tube.collection_date || '';
    document.getElementById('raptor-age').value = tube.age || '';

    const sex = tube.sex || 'Unknown';
    const sexRadio = document.querySelector(`input[name="raptor-sex"][value="${sex}"]`);
    if (sexRadio) sexRadio.checked = true;

    document.getElementById('raptor-freeze-thaw').value = tube.freeze_thaw_cycles || 0;
    document.getElementById('raptor-wrmd').value = tube.wrmd_number || '';
    document.getElementById('raptor-vmth').value = tube.vmth_number || '';
    document.getElementById('raptor-notes').value = tube.notes || '';
    document.getElementById('btn-raptor-delete').style.display = 'inline-block';
    document.getElementById('btn-raptor-thaw').style.display = 'inline-block';
    document.getElementById('btn-raptor-print').style.display = 'inline-block';

    // Store tube data for printing
    document.getElementById('raptorTubeModal').dataset.tubeData = JSON.stringify(tube);

    new bootstrap.Modal(document.getElementById('raptorTubeModal')).show();
}

async function saveRaptorTube() {
    const dbId = document.getElementById('raptor-tube-db-id').value;
    const sex = document.querySelector('input[name="raptor-sex"]:checked')?.value || 'Unknown';

    const data = {
        box_id: parseInt(document.getElementById('raptor-tube-box-id').value),
        row_pos: parseInt(document.getElementById('raptor-tube-row').value),
        col_pos: parseInt(document.getElementById('raptor-tube-col').value),
        species_id: parseInt(document.getElementById('raptor-species').value),
        collection_date: document.getElementById('raptor-collection-date').value,
        age: document.getElementById('raptor-age').value,
        sex: sex,
        freeze_thaw_cycles: parseInt(document.getElementById('raptor-freeze-thaw').value) || 0,
        wrmd_number: document.getElementById('raptor-wrmd').value.trim(),
        vmth_number: document.getElementById('raptor-vmth').value.trim(),
        notes: document.getElementById('raptor-notes').value.trim(),
    };

    if (!data.species_id) {
        showToast('Please select a species', 'error');
        return;
    }
    if (!data.collection_date) {
        showToast('Please enter a collection date', 'error');
        return;
    }

    try {
        let result;
        if (dbId) {
            result = await API.put(`/api/raptor/tubes/${dbId}`, data);
            showToast('Sample updated successfully');
        } else {
            result = await API.post('/api/raptor/tubes', data);
            showToast(`Sample ${result.tube_id} created successfully`);
        }
        bootstrap.Modal.getInstance(document.getElementById('raptorTubeModal')).hide();
        onRaptorBoxClick(currentRaptorBoxId);
        loadRaptorQuickStats();
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

async function deleteRaptorTube() {
    const dbId = document.getElementById('raptor-tube-db-id').value;
    if (!dbId) return;
    if (!confirm('Are you sure you want to remove this sample? This cannot be undone.')) return;

    try {
        await API.del(`/api/raptor/tubes/${dbId}`);
        showToast('Sample removed');
        bootstrap.Modal.getInstance(document.getElementById('raptorTubeModal')).hide();
        onRaptorBoxClick(currentRaptorBoxId);
        loadRaptorQuickStats();
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

async function recordThaw() {
    const dbId = document.getElementById('raptor-tube-db-id').value;
    if (!dbId) return;

    try {
        const result = await API.put(`/api/raptor/tubes/${dbId}/thaw`);
        document.getElementById('raptor-freeze-thaw').value = result.freeze_thaw_cycles;
        showToast(`Freeze-thaw cycle recorded (now ${result.freeze_thaw_cycles})`);
        onRaptorBoxClick(currentRaptorBoxId);
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

async function printRaptorLabel() {
    try {
        const tubeData = JSON.parse(document.getElementById('raptorTubeModal').dataset.tubeData || '{}');
        if (!tubeData.tube_id) {
            showToast('No tube data available for printing', 'error');
            return;
        }
        const img = generateRaptorLabel(tubeData);
        await printLabel(img);
        showToast('Label sent to printer');
    } catch (err) {
        showToast('Print error: ' + err.message, 'error');
    }
}

async function addNewSpecies() {
    const common = document.getElementById('new-species-common').value.trim();
    const scientific = document.getElementById('new-species-scientific').value.trim();
    const code = document.getElementById('new-species-code').value.trim().toUpperCase();

    if (!common || !scientific || !code) {
        showToast('All fields are required', 'error');
        return;
    }
    if (code.length !== 4) {
        showToast('Banding code must be exactly 4 letters', 'error');
        return;
    }

    try {
        await API.post('/api/species', {
            common_name: common,
            scientific_name: scientific,
            banding_code: code,
        });
        showToast(`Species ${code} added`);
        bootstrap.Modal.getInstance(document.getElementById('addSpeciesModal')).hide();

        // Refresh species list
        speciesList = await API.get('/api/species');
        populateSpeciesDropdown();

        // Clear form
        document.getElementById('new-species-common').value = '';
        document.getElementById('new-species-scientific').value = '';
        document.getElementById('new-species-code').value = '';
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

async function onRaptorSearch() {
    const q = document.getElementById('raptor-search').value.trim();
    const dropdown = document.getElementById('raptor-search-results');
    if (!q) {
        dropdown.classList.remove('show');
        return;
    }
    try {
        const results = await API.get(`/api/raptor/search?q=${encodeURIComponent(q)}`);
        if (results.length === 0) {
            dropdown.innerHTML = '<div class="search-result-item text-muted">No results found</div>';
        } else {
            dropdown.innerHTML = results.map(r => `
                <div class="search-result-item" onclick="onRaptorBoxClick(${r.box_id})">
                    <strong>${r.tube_id}</strong>
                    <span class="badge bg-secondary ms-1">${r.banding_code}</span>
                    <span class="text-muted ms-2">${r.common_name}</span>
                    <br>
                    <small class="text-muted">
                        ${r.rack_label} / ${r.box_label} / ${positionLabel(r.row_pos, r.col_pos)}
                        ${r.wrmd_number ? ' | WRMD: ' + r.wrmd_number : ''}
                    </small>
                </div>
            `).join('');
        }
        dropdown.classList.add('show');
    } catch (err) {
        console.error('Search failed:', err);
    }
}
