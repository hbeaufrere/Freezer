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
    document.getElementById('btn-raptor-rebird').addEventListener('click', reassignRaptorTube);

    document.querySelectorAll('input[name="raptor-bird-mode"]').forEach((radio) => {
        radio.addEventListener('change', () => setBirdMode(radio.value));
    });
    document.getElementById('btn-raptor-bird-find').addEventListener('click', findBird);
    document.getElementById('raptor-bird-id').addEventListener('keydown', (event) => {
        if (event.key === 'Enter') { event.preventDefault(); findBird(); }
    });

    document.addEventListener('retrievallogged', onRaptorRetrievalLogged);

    // Renaming a rack changes what "Other Species" excludes elsewhere, so
    // the cached list of designations follows the edit.
    document.addEventListener('rackrenamed', async () => {
        const fresh = await API.get('/api/freezer').catch(() => null);
        if (!fresh) return;
        rackDesignations = fresh
            .filter((s) => s.section === 'raptor')
            .flatMap((s) => s.racks.map((r) => r.designation).filter(Boolean));
    });

    const sampleType = document.getElementById('raptor-sample-type');
    sampleType.addEventListener('change', syncSampleTypeHint);
    document.getElementById('btn-add-species').addEventListener('click', addNewSpecies);

    attachCopyButton(document.getElementById('btn-copy-tube-id'),
                     () => document.getElementById('raptor-tube-id-badge').textContent);
}

/* ---- Species filtering by rack designation ---------------- */

/* Species codes anywhere in a rack's name. Now that the line is free text,
   "RTHA / RSHA — plasma only" has to yield both hawks, so tokens are matched
   wherever they sit — and checked against the real species list, so a
   capitalised WITH or FROM cannot pass as a bird. */
function parseDesignationCodes(designation) {
    const known = new Set(speciesList.map((s) => s.banding_code));
    return (designation.match(/\b[A-Z]{4}\b/g) || []).filter((code) => known.has(code));
}

function isOwl(species) {
    return species.common_name.toLowerCase().includes('owl');
}

/* Racks carry a designation like "RTHA / RSHA / SWHA". The form offers only
   those species, so a hawk cannot be filed in the owl rack by accident.
   Returns null — anything may go in — when the rack has no designation, or
   when its name carries no species codes at all: a rack renamed "Kestrel PK
   study" has opted out of the narrowing, not into an empty list. */
function getAllowedSpecies(designation) {
    if (!designation) return null;
    if (designation !== 'Other Species'
        && !designation.includes('Other Owls')
        && parseDesignationCodes(designation).length === 0) {
        return null;
    }

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

/* A retrieval changes the tube under the open modal, so the modal has to
   follow: either the sample has left the freezer and the sheet should go with
   it, or it went back and its freeze-thaw count has just gone up. */
function onRaptorRetrievalLogged(event) {
    const detail = event.detail || {};
    if (detail.section !== 'raptor') return;

    if (detail.tubeRemoved) {
        bootstrap.Modal.getInstance(document.getElementById('raptorTubeModal'))?.hide();
    } else if (detail.freezeThawCycles !== null && detail.freezeThawCycles !== undefined) {
        document.getElementById('raptor-freeze-thaw').value = detail.freezeThawCycles;
    }

    if (currentRaptorBoxId) openRaptorBox(currentRaptorBoxId);
    loadRaptorQuickStats();
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
    document.getElementById('raptor-blood-timing').value = '';
    document.getElementById('raptor-anticoagulant').value = '';
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
    setRaptorHidden('btn-raptor-rebird', true);

    setRaptorHidden('raptor-bird-mode', false);
    document.getElementById('raptor-bird-new').checked = true;
    setBirdMode('new');

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
    document.getElementById('raptor-blood-timing').value = tube.blood_timing || '';
    document.getElementById('raptor-anticoagulant').value = tube.anticoagulant || '';
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
    setRaptorHidden('btn-raptor-rebird', false);

    setRaptorHidden('raptor-bird-mode', true);
    linkedBird = null;
    setBirdFieldsLocked(false);
    document.getElementById('raptor-species').disabled = true;

    document.getElementById('raptorTubeModal').dataset.tubeData = JSON.stringify(tube);
    bootstrap.Modal.getOrCreateInstance(document.getElementById('raptorTubeModal')).show();
}

async function saveRaptorTube() {
    const dbId = document.getElementById('raptor-tube-db-id').value;
    const joiningBird = !dbId && birdMode() === 'existing';

    if (joiningBird && !linkedBird) {
        document.getElementById('raptor-bird-id').focus();
        return showToast('Find the bird first, so the new tube takes its ID.', 'error');
    }

    const speciesId = parseInt(document.getElementById('raptor-species').value, 10);
    const collectionDate = document.getElementById('raptor-collection-date').value;
    const sampleType = document.getElementById('raptor-sample-type').value;
    const bloodTiming = document.getElementById('raptor-blood-timing').value;
    const wrmd = document.getElementById('raptor-wrmd').value.trim();
    const vmth = document.getElementById('raptor-vmth').value.trim();

    if (!joiningBird && !speciesId) return showToast('Choose a species first.', 'error');
    if (!collectionDate) return showToast('Enter the collection date.', 'error');
    if (isBloodType(sampleType) && !bloodTiming) {
        document.getElementById('raptor-blood-timing').focus();
        return showToast('Say when the blood was drawn: intake, under care or pre-release.', 'error');
    }
    // In "same bird" mode the case numbers come from the bird and are locked.
    if (!joiningBird && !wrmd && !vmth) {
        document.getElementById('raptor-wrmd').focus();
        return showToast('Enter a WRMD or VMACS number — one of the two is required.', 'error');
    }

    const payload = {
        box_id: parseInt(document.getElementById('raptor-tube-box-id').value, 10),
        row_pos: parseInt(document.getElementById('raptor-tube-row').value, 10),
        col_pos: parseInt(document.getElementById('raptor-tube-col').value, 10),
        sample_type: sampleType,
        blood_timing: isBloodType(sampleType) ? bloodTiming : '',
        anticoagulant: isBloodType(sampleType)
            ? document.getElementById('raptor-anticoagulant').value : '',
        collection_date: collectionDate,
        freeze_thaw_cycles: parseInt(document.getElementById('raptor-freeze-thaw').value, 10) || 0,
        notes: document.getElementById('raptor-notes').value.trim(),
    };

    if (joiningBird) {
        // The bird's own facts are not sent: the server takes them from the
        // bird, so one bird cannot drift into two descriptions.
        payload.bird_id = linkedBird.bird_id;
    } else {
        Object.assign(payload, {
            species_id: speciesId,
            age: document.getElementById('raptor-age').value,
            sex: document.querySelector('input[name="raptor-sex"]:checked')?.value || 'Unknown',
            wrmd_number: wrmd,
            vmth_number: vmth,
        });
    }

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
            const made = result.tubes || [result];
            const first = made[0].tube_id;
            const last = made[made.length - 1].tube_id;
            if (joiningBird) {
                showToast(made.length === 1
                    ? `${first} added to ${linkedBird.bird_id} (${linkedBird.common_name})`
                    : `${first} to ${last} added to ${linkedBird.bird_id}`);
            } else if (made.length > 1) {
                showToast(`${made.length} tubes created: ${first} to ${last}`);
            } else {
                showToast(`Sample ${first} created`);
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
    if (!confirm(reconcileWarning(tubeId))) return;

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
/* ---- One bird, several sample types ------------------------ */

/* The bird the tube being added belongs to, once found. Null in "new bird"
   mode or before a lookup has succeeded. */
let linkedBird = null;

function birdMode() {
    return document.querySelector('input[name="raptor-bird-mode"]:checked')?.value || 'new';
}

/* Species, age, sex and case numbers describe the animal, not the tube.
   When the tube joins a bird already on file they come from that bird and
   are shown locked, so what you see is what will be stored. */
function setBirdFieldsLocked(locked) {
    // Not the collection date: a pre-release sample is drawn weeks after the
    // intake one, so that field belongs to the tube and stays open.
    ['raptor-age', 'raptor-wrmd', 'raptor-vmth']
        .forEach((id) => { document.getElementById(id).disabled = locked; });
    document.querySelectorAll('input[name="raptor-sex"]')
        .forEach((radio) => { radio.disabled = locked; });
    document.getElementById('raptor-species').disabled = locked;
}

function setBirdMode(mode) {
    const existing = mode === 'existing';
    setRaptorHidden('raptor-bird-lookup', !existing);
    linkedBird = null;
    document.getElementById('raptor-bird-card').hidden = true;

    if (existing) {
        setBirdFieldsLocked(true);
        const input = document.getElementById('raptor-bird-id');
        input.value = '';
        setTimeout(() => input.focus(), 50);
    } else {
        setBirdFieldsLocked(false);
    }
}

async function findBird() {
    const input = document.getElementById('raptor-bird-id');
    const card = document.getElementById('raptor-bird-card');
    const wanted = input.value.trim().toUpperCase();
    if (!wanted) return;

    let bird;
    try {
        bird = await API.get(`/api/raptor/birds/${encodeURIComponent(wanted)}`);
    } catch (err) {
        linkedBird = null;
        card.hidden = false;
        card.className = 'bird-card is-missing';
        card.innerHTML = `<i class="bi bi-question-circle me-1"></i>${escapeHtml(err.message)}`;
        return;
    }

    linkedBird = bird;
    input.value = bird.bird_id;

    // Fill the locked fields from the bird so the form shows the truth.
    populateSpeciesDropdown(null);
    document.getElementById('raptor-species').value = bird.species_id;
    document.getElementById('raptor-collection-date').value = bird.collection_date || '';
    document.getElementById('raptor-age').value = bird.age || '';
    const sexRadio = document.querySelector(
        `input[name="raptor-sex"][value="${bird.sex || 'Unknown'}"]`);
    if (sexRadio) sexRadio.checked = true;
    document.getElementById('raptor-wrmd').value = bird.wrmd_number || '';
    document.getElementById('raptor-vmth').value = bird.vmth_number || '';

    const has = bird.tubes.map((t) =>
        `<span class="bird-tube">${escapeHtml(t.sample_type || 'Plasma')}
            <small>${escapeHtml(t.box_label)} · ${positionLabel(t.row_pos, t.col_pos)}</small></span>`
    ).join('');

    card.hidden = false;
    card.className = 'bird-card';
    card.innerHTML = `
        <div class="bird-card-head">
            <strong>${escapeHtml(bird.common_name)}</strong>
            <span class="text-body-secondary">
                collected ${escapeHtml(bird.collection_date || '—')}
                ${bird.age ? ' · ' + escapeHtml(bird.age) : ''}
                ${bird.sex && bird.sex !== 'Unknown' ? ' · ' + escapeHtml(bird.sex) : ''}
            </span>
        </div>
        <div class="bird-card-tubes">Already has: ${has}</div>
        <div class="bird-card-next">
            This tube will be <span class="font-monospace fw-semibold">${escapeHtml(bird.next_tube_id)}</span>
        </div>`;
}

/* A tube filed as a bird of its own that should have joined another one.
   Renames it to the next suffix under that bird and takes the bird's facts;
   the old ID is kept in the notes because it is printed on the tube. */
async function reassignRaptorTube() {
    const dbId = document.getElementById('raptor-tube-db-id').value;
    const current = document.getElementById('raptor-tube-id-badge').textContent;
    if (!dbId) return;

    const typed = prompt(
        `${current} belongs to which bird?\n\nEnter the ID of any sample from that bird `
        + '(e.g. RTHA26001 or RTHA26001-2).');
    if (!typed) return;

    let bird;
    try {
        bird = await API.get(`/api/raptor/birds/${encodeURIComponent(typed.trim())}`);
    } catch (err) {
        return showToast(err.message, 'error');
    }

    const ok = confirm(
        `${current} → ${bird.next_tube_id}\n\n`
        + `It becomes a tube of ${bird.bird_id} (${bird.common_name}, collected `
        + `${bird.collection_date || '—'}) and takes that bird's age, sex, WRMD and VMTH `
        + 'numbers. Its box, position, sample type and freeze-thaw count stay as they are.\n\n'
        + `The tube in the freezer is still labelled ${current}. Reprint the label; `
        + 'until then, searching the old ID will still find it.');
    if (!ok) return;

    try {
        const moved = await API.put(`/api/raptor/tubes/${dbId}/bird`, { bird_id: bird.bird_id });
        showToast(`${moved.previous_tube_id} is now ${moved.tube_id} — reprint its label`);
        bootstrap.Modal.getInstance(document.getElementById('raptorTubeModal')).hide();
        await openRaptorBox(currentRaptorBoxId);
        loadRaptorQuickStats();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

const BLOOD_TYPES = ['Plasma', 'Packed RBCs'];

function isBloodType(value) {
    return BLOOD_TYPES.includes(value);
}

/* The sample type decides which of the row's other fields apply: blood gets
   timing and anticoagulant, "Other" gets the reminder to describe it. */
function syncSampleTypeHint() {
    const value = document.getElementById('raptor-sample-type').value;
    const blood = isBloodType(value);
    document.querySelectorAll('.raptor-blood-only').forEach((el) => { el.hidden = !blood; });
    document.getElementById('raptor-sample-type-hint-wrap').hidden = value !== 'Other';
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
