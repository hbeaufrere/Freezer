/* Raptor Biobank page. */

let currentRaptorBoxId = null;
let currentRaptorBox = null;
let speciesList = [];
let rackDesignations = [];

async function initRaptorPage() {
    speciesList = await API.get('/api/species');
    populateSpeciesDropdown(null);

    const shelves = await renderSectionSidebar('raptor-rack-sidebar', 'raptor', openRaptorBox);
    if (shelves) {
        rackDesignations = shelves
            .filter((s) => s.section === 'raptor')
            .flatMap((s) => s.racks.map((r) => r.designation).filter(Boolean));
    }

    loadRaptorQuickStats();

    const preselected = new URLSearchParams(window.location.search).get('box');
    if (preselected) openRaptorBox(parseInt(preselected, 10));

    const search = document.getElementById('raptor-search');
    const dropdown = document.getElementById('raptor-search-results');
    search.addEventListener('input', debounce(runRaptorSearch, 250));
    search.addEventListener('blur', () => setTimeout(() => {
        dropdown.classList.remove('show');
        search.setAttribute('aria-expanded', 'false');
    }, 150));
    attachSearchKeys(search, dropdown);

    document.getElementById('btn-raptor-save').addEventListener('click', saveRaptorTube);
    document.getElementById('btn-raptor-delete').addEventListener('click', deleteRaptorTube);
    document.getElementById('btn-raptor-thaw').addEventListener('click', recordRaptorThaw);
    document.getElementById('btn-raptor-barcode').addEventListener('click', showRaptorBarcode);
    document.getElementById('btn-raptor-retrieve').addEventListener('click', logRaptorRetrieval);

    const sampleType = document.getElementById('raptor-sample-type');
    sampleType.addEventListener('change', syncSampleTypeHint);
    document.getElementById('btn-add-species').addEventListener('click', addNewSpecies);

    attachCopyButton(document.getElementById('btn-copy-tube-id'),
                     () => document.getElementById('raptor-tube-id-badge').textContent);
}

/* ---- Species filtering by rack designation ---------------- */

function parseDesignationCodes(designation) {
    return designation.split(' / ').map((s) => s.trim()).filter((s) => /^[A-Z]{4}$/.test(s));
}

function isOwl(species) {
    return species.common_name.toLowerCase().includes('owl');
}

/* Racks carry a designation like "RTHA / RSHA / SWHA". The form offers only
   those species, so a hawk cannot be filed in the owl rack by accident.
   Returns null when the rack has no designation and anything may go in it. */
function getAllowedSpecies(designation) {
    if (!designation) return null;

    if (designation === 'Other Species') {
        const claimed = new Set();
        rackDesignations.forEach((d) => {
            if (d === 'Other Species') return;
            parseDesignationCodes(d).forEach((code) => claimed.add(code));
            if (d.includes('Other Owls')) {
                speciesList.filter(isOwl).forEach((s) => claimed.add(s.banding_code));
            }
        });
        return speciesList.filter((s) => !claimed.has(s.banding_code));
    }

    const codes = parseDesignationCodes(designation);
    let allowed = speciesList.filter((s) => codes.includes(s.banding_code));

    if (designation.includes('Other Owls')) {
        const owlsElsewhere = new Set();
        rackDesignations.forEach((d) => {
            if (d === designation) return;
            parseDesignationCodes(d).forEach((code) => {
                const species = speciesList.find((s) => s.banding_code === code);
                if (species && isOwl(species)) owlsElsewhere.add(code);
            });
        });
        allowed = allowed.concat(speciesList.filter(
            (s) => isOwl(s) && !owlsElsewhere.has(s.banding_code) && !codes.includes(s.banding_code)
        ));
    }

    return allowed;
}

function populateSpeciesDropdown(designation) {
    const select = document.getElementById('raptor-species');
    const previous = select.value;
    select.textContent = '';

    const placeholder = new Option('Select a species…', '');
    select.appendChild(placeholder);

    (getAllowedSpecies(designation) || speciesList).forEach((species) => {
        const option = new Option(
            `${species.banding_code} — ${species.common_name}`, species.id
        );
        option.title = species.scientific_name;
        select.appendChild(option);
    });

    select.appendChild(new Option('+ Add a new species…', '__new__'));
    select.value = previous;

    if (!select.dataset.wired) {
        select.dataset.wired = 'true';
        select.addEventListener('change', () => {
            if (select.value === '__new__') {
                select.value = '';
                bootstrap.Modal.getOrCreateInstance(
                    document.getElementById('addSpeciesModal')
                ).show();
            }
        });
    }
}

async function loadRaptorQuickStats() {
    try {
        const stats = await API.get('/api/stats/raptor');
        document.getElementById('raptor-stat-total').textContent = stats.total_samples;
        document.getElementById('raptor-stat-species').textContent =
            (stats.species_breakdown || []).length;
    } catch (err) {
        console.error('Raptor stats failed to load:', err);
    }
}

/* ---- Box view --------------------------------------------- */

async function openRaptorBox(boxId) {
    currentRaptorBoxId = boxId;

    document.querySelectorAll('#raptor-rack-sidebar .box-slot')
        .forEach((el) => el.classList.remove('selected'));
    document.querySelector(`#raptor-rack-sidebar .box-slot[data-box-id="${boxId}"]`)
        ?.classList.add('selected');

    try {
        const box = await API.get(`/api/boxes/${boxId}`);
        currentRaptorBox = box;

        const crumb = document.getElementById('raptor-breadcrumb');
        crumb.innerHTML =
            `<button type="button" onclick="window.location.href='/raptor'">${escapeHtml(box.shelf_name)}</button>` +
            `<span>&rsaquo;</span><span>${escapeHtml(box.rack_label)}</span>` +
            `<span>&rsaquo;</span><span>${escapeHtml(box.drawer_label)}</span>` +
            `<span>&rsaquo;</span><strong>${escapeHtml(box.label)}</strong>` +
            (box.rack_designation
                ? `<span class="ms-1 text-body-secondary">(${escapeHtml(box.rack_designation)})</span>`
                : '');

        const legendData = renderBoxGrid(document.getElementById('raptor-grid-area'), box, {
            onTubeClick: openRaptorEditModal,
            onEmptyClick: openRaptorAddModal,
        });

        renderSpeciesLegend(legendData);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderSpeciesLegend(legendData) {
    const legend = document.getElementById('raptor-species-legend');
    const entries = legendData ? Object.entries(legendData.speciesIndexMap) : [];

    if (!entries.length) {
        legend.hidden = true;
        legend.textContent = '';
        return;
    }

    legend.innerHTML = entries.map(([code, index]) => {
        const species = speciesList.find((s) => s.banding_code === code);
        const name = species ? species.common_name : code;
        return `<span class="species-chip">
            <span class="dot species-${index % 12}"></span>
            <code>${escapeHtml(code)}</code>${escapeHtml(name)}
        </span>`;
    }).join('');
    legend.hidden = false;
}

/* ---- Modal ------------------------------------------------ */

function setRaptorHidden(id, hidden) {
    document.getElementById(id).hidden = hidden;
}

function openRaptorAddModal(row, col) {
    document.getElementById('raptorTubeModalTitle').textContent = 'Add raptor sample';
    document.getElementById('raptor-tube-db-id').value = '';
    document.getElementById('raptor-tube-box-id').value = currentRaptorBoxId;
    document.getElementById('raptor-tube-row').value = row;
    document.getElementById('raptor-tube-col').value = col;
    document.getElementById('raptor-tube-position').textContent =
        `${currentRaptorBox.label} · ${positionLabel(row, col)}`;

    setRaptorHidden('raptor-tube-id-display', true);

    populateSpeciesDropdown(currentRaptorBox.rack_designation || null);
    const speciesSelect = document.getElementById('raptor-species');
    speciesSelect.value = '';
    speciesSelect.disabled = false;

    document.getElementById('raptor-collection-date').value = today();
    document.getElementById('raptor-sample-type').value = 'Plasma';
    syncSampleTypeHint();
    document.getElementById('raptor-age').value = '';
    document.getElementById('raptor-sex-u').checked = true;
    document.getElementById('raptor-freeze-thaw').value = 0;
    document.getElementById('raptor-wrmd').value = '';
    document.getElementById('raptor-vmth').value = '';
    document.getElementById('raptor-notes').value = '';
    document.getElementById('raptor-num-tubes').value = 1;

    setRaptorHidden('raptor-num-tubes-group', false);
    setRaptorHidden('btn-raptor-delete', true);
    setRaptorHidden('btn-raptor-thaw', true);
    setRaptorHidden('btn-raptor-barcode', true);
    setRaptorHidden('btn-raptor-retrieve', true);

    bootstrap.Modal.getOrCreateInstance(document.getElementById('raptorTubeModal')).show();
}

function openRaptorEditModal(tube, row, col) {
    document.getElementById('raptorTubeModalTitle').textContent = 'Edit raptor sample';
    document.getElementById('raptor-tube-db-id').value = tube.id;
    document.getElementById('raptor-tube-box-id').value = tube.box_id;
    document.getElementById('raptor-tube-row').value = row;
    document.getElementById('raptor-tube-col').value = col;
    document.getElementById('raptor-tube-position').textContent =
        `${currentRaptorBox.label} · ${positionLabel(row, col)}`;

    document.getElementById('raptor-tube-id-badge').textContent = tube.tube_id;
    setRaptorHidden('raptor-tube-id-display', false);

    // Species is fixed once an ID has been issued against it.
    populateSpeciesDropdown(null);
    const speciesSelect = document.getElementById('raptor-species');
    speciesSelect.value = tube.species_id;
    speciesSelect.disabled = true;

    document.getElementById('raptor-collection-date').value = tube.collection_date || '';
    document.getElementById('raptor-sample-type').value = tube.sample_type || 'Plasma';
    syncSampleTypeHint();
    document.getElementById('raptor-age').value = tube.age || '';
    const sexRadio = document.querySelector(
        `input[name="raptor-sex"][value="${tube.sex || 'Unknown'}"]`
    );
    if (sexRadio) sexRadio.checked = true;
    document.getElementById('raptor-freeze-thaw').value = tube.freeze_thaw_cycles || 0;
    document.getElementById('raptor-wrmd').value = tube.wrmd_number || '';
    document.getElementById('raptor-vmth').value = tube.vmth_number || '';
    document.getElementById('raptor-notes').value = tube.notes || '';

    setRaptorHidden('raptor-num-tubes-group', true);
    setRaptorHidden('btn-raptor-delete', false);
    setRaptorHidden('btn-raptor-thaw', false);
    setRaptorHidden('btn-raptor-barcode', false);
    setRaptorHidden('btn-raptor-retrieve', false);

    document.getElementById('raptorTubeModal').dataset.tubeData = JSON.stringify(tube);
    bootstrap.Modal.getOrCreateInstance(document.getElementById('raptorTubeModal')).show();
}

async function saveRaptorTube() {
    const dbId = document.getElementById('raptor-tube-db-id').value;
    const speciesId = parseInt(document.getElementById('raptor-species').value, 10);
    const collectionDate = document.getElementById('raptor-collection-date').value;

    if (!speciesId) return showToast('Choose a species first.', 'error');
    if (!collectionDate) return showToast('Enter the collection date.', 'error');

    const payload = {
        box_id: parseInt(document.getElementById('raptor-tube-box-id').value, 10),
        row_pos: parseInt(document.getElementById('raptor-tube-row').value, 10),
        col_pos: parseInt(document.getElementById('raptor-tube-col').value, 10),
        species_id: speciesId,
        collection_date: collectionDate,
        sample_type: document.getElementById('raptor-sample-type').value,
        age: document.getElementById('raptor-age').value,
        sex: document.querySelector('input[name="raptor-sex"]:checked')?.value || 'Unknown',
        freeze_thaw_cycles: parseInt(document.getElementById('raptor-freeze-thaw').value, 10) || 0,
        wrmd_number: document.getElementById('raptor-wrmd').value.trim(),
        vmth_number: document.getElementById('raptor-vmth').value.trim(),
        notes: document.getElementById('raptor-notes').value.trim(),
    };

    if (!dbId) {
        payload.num_tubes = parseInt(document.getElementById('raptor-num-tubes').value, 10) || 1;
    }

    const button = document.getElementById('btn-raptor-save');
    button.disabled = true;
    try {
        if (dbId) {
            await API.put(`/api/raptor/tubes/${dbId}`, payload);
            showToast('Sample updated');
        } else {
            const result = await API.post('/api/raptor/tubes', payload);
            if (result.tubes) {
                const first = result.tubes[0].tube_id;
                const last = result.tubes[result.tubes.length - 1].tube_id;
                showToast(`${result.tubes.length} tubes created: ${first} to ${last}`);
            } else {
                showToast(`Sample ${result.tube_id} created`);
            }
        }
        bootstrap.Modal.getInstance(document.getElementById('raptorTubeModal')).hide();
        await openRaptorBox(currentRaptorBoxId);
        loadRaptorQuickStats();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        button.disabled = false;
    }
}

async function recordRaptorThaw() {
    const dbId = document.getElementById('raptor-tube-db-id').value;
    if (!dbId) return;
    try {
        const tube = await API.put(`/api/raptor/tubes/${dbId}/thaw`);
        document.getElementById('raptor-freeze-thaw').value = tube.freeze_thaw_cycles;
        showToast(`Freeze-thaw cycle recorded — now ${tube.freeze_thaw_cycles}`);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function deleteRaptorTube() {
    const dbId = document.getElementById('raptor-tube-db-id').value;
    if (!dbId) return;

    const tubeId = document.getElementById('raptor-tube-id-badge').textContent || 'this sample';
    if (!confirm(`Remove ${tubeId} from the biobank record? This cannot be undone.`)) return;

    try {
        await API.del(`/api/raptor/tubes/${dbId}`);
        showToast('Sample removed');
        bootstrap.Modal.getInstance(document.getElementById('raptorTubeModal')).hide();
        await openRaptorBox(currentRaptorBoxId);
        loadRaptorQuickStats();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

/* "Other" only means anything if the tissue is written down, so say so. */
function syncSampleTypeHint() {
    const value = document.getElementById('raptor-sample-type').value;
    document.getElementById('raptor-sample-type-hint').hidden = value !== 'Other';
}

function logRaptorRetrieval() {
    const tube = JSON.parse(
        document.getElementById('raptorTubeModal').dataset.tubeData || '{}'
    );
    openRetrievalModal('raptor', tube.id, `${tube.tube_id} · ${tube.common_name}`);
}

function showRaptorBarcode() {
    const tube = JSON.parse(
        document.getElementById('raptorTubeModal').dataset.tubeData || '{}'
    );
    if (!tube.tube_id) {
        showToast('Save the sample first — the tube ID is issued on save.', 'warning');
        return;
    }
    showLabelBarcode(tube.tube_id, `${tube.common_name} · ${tube.sample_type || 'Plasma'}`);
}

async function addNewSpecies() {
    const common = document.getElementById('new-species-common').value.trim();
    const scientific = document.getElementById('new-species-scientific').value.trim();
    const code = document.getElementById('new-species-code').value.trim().toUpperCase();

    if (!common || !scientific || !code) {
        return showToast('Fill in all three fields.', 'error');
    }
    if (!/^[A-Z]{4}$/.test(code)) {
        return showToast('The banding code must be exactly four letters.', 'error');
    }

    try {
        await API.post('/api/species', {
            common_name: common, scientific_name: scientific, banding_code: code,
        });
        showToast(`${code} added`);
        bootstrap.Modal.getInstance(document.getElementById('addSpeciesModal')).hide();

        speciesList = await API.get('/api/species');
        populateSpeciesDropdown(currentRaptorBox ? currentRaptorBox.rack_designation : null);

        document.getElementById('new-species-common').value = '';
        document.getElementById('new-species-scientific').value = '';
        document.getElementById('new-species-code').value = '';
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function runRaptorSearch() {
    const input = document.getElementById('raptor-search');
    const dropdown = document.getElementById('raptor-search-results');
    const query = input.value.trim();

    if (!query) {
        dropdown.classList.remove('show');
        input.setAttribute('aria-expanded', 'false');
        return;
    }

    try {
        const results = await API.get(`/api/raptor/search?q=${encodeURIComponent(query)}`);
        dropdown.textContent = '';

        if (!results.length) {
            dropdown.innerHTML = '<div class="search-empty">No samples match that search.</div>';
        } else {
            results.forEach((row) => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'search-result-item';
                item.dataset.selectable = 'true';
                item.setAttribute('role', 'option');
                item.innerHTML = `
                    <span class="result-id">${escapeHtml(row.tube_id)}</span>
                    <span class="text-body-secondary ms-2">${escapeHtml(row.common_name)}</span>
                    <div class="result-meta">
                        ${escapeHtml(row.rack_label)} · ${escapeHtml(row.box_label)} ·
                        ${positionLabel(row.row_pos, row.col_pos)}
                        ${row.wrmd_number ? '· WRMD ' + escapeHtml(row.wrmd_number) : ''}
                    </div>`;
                item.addEventListener('click', () => {
                    dropdown.classList.remove('show');
                    openRaptorBox(row.box_id);
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
