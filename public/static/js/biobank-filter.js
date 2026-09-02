/* "Have we got any of these, and where are they?" — the question the biobank
   exists to answer, asked directly rather than by scrolling boxes.

   The count, the list and the download all come from one query on the server,
   so the number on screen is always the number of rows you get. */

const filterState = { species_id: '', sample_type: '', sex: '', age: '' };

const FILTER_FIELDS = {
    species_id: 'filter-species',
    sample_type: 'filter-sample-type',
    sex: 'filter-sex',
    age: 'filter-age',
};

async function initBiobankFilter() {
    if (!document.getElementById('biobank-filter')) return;

    await loadFilterOptions();

    Object.entries(FILTER_FIELDS).forEach(([field, id]) => {
        document.getElementById(id).addEventListener('change', (event) => {
            filterState[field] = event.target.value;
            runBiobankFilter();
        });
    });

    document.getElementById('btn-filter-clear').addEventListener('click', clearBiobankFilter);
    document.getElementById('btn-filter-csv')
        .addEventListener('click', () => downloadFiltered('csv'));
    document.getElementById('btn-filter-xlsx')
        .addEventListener('click', () => downloadFiltered('xlsx'));

    runBiobankFilter();
}

/* Options come from what is actually in the freezer, with counts, so you can
   see there is no liver before spending a click finding out. */
async function loadFilterOptions() {
    let options;
    try {
        options = await API.get('/api/raptor/filter-options');
    } catch (err) {
        showToast(err.message, 'error');
        return;
    }

    fillOptions('filter-species', options.species.map((s) => ({
        value: s.id,
        label: `${s.common_name} (${s.banding_code})`,
        count: s.count,
    })));

    [['filter-sample-type', options.sample_types],
     ['filter-sex', options.sexes],
     ['filter-age', options.ages]].forEach(([id, values]) => {
        fillOptions(id, values.map((v) => ({
            value: v.value, label: v.value, count: v.count,
        })));
    });
}

function fillOptions(selectId, entries) {
    const select = document.getElementById(selectId);
    // Keep the "Any …" option, replace the rest.
    while (select.options.length > 1) select.remove(1);

    entries.forEach((entry) => {
        const option = document.createElement('option');
        option.value = entry.value;
        option.textContent = `${entry.label} · ${entry.count}`;
        select.appendChild(option);
    });

    select.disabled = entries.length === 0;
}

function filterParams() {
    const params = new URLSearchParams();
    Object.entries(filterState).forEach(([field, value]) => {
        if (value) params.set(field, value);
    });
    return params;
}

async function runBiobankFilter() {
    const results = document.getElementById('filter-results');
    const note = document.getElementById('filter-note');

    let data;
    try {
        data = await API.get(`/api/raptor/filter?${filterParams()}`);
    } catch (err) {
        showToast(err.message, 'error');
        return;
    }

    document.getElementById('filter-count').textContent = data.matched.toLocaleString();
    document.getElementById('filter-count-label').textContent =
        `${data.matched === 1 ? 'sample' : 'samples'} from `
        + `${data.birds} ${data.birds === 1 ? 'bird' : 'birds'}`;

    const empty = data.matched === 0;
    document.getElementById('btn-filter-csv').disabled = empty;
    document.getElementById('btn-filter-xlsx').disabled = empty;

    if (empty) {
        results.innerHTML = `
            <div class="empty-state border-0 py-4">
                <i class="bi bi-search empty-icon"></i>
                <div class="empty-title">Nothing matches those criteria</div>
                <div class="empty-hint">Widen one of them, or clear the filter.</div>
            </div>`;
        note.hidden = true;
        return;
    }

    results.innerHTML = `
        <table class="table table-sm align-middle filter-table">
            <thead>
                <tr>
                    <th>Tube ID</th><th>Species</th><th>Type</th>
                    <th>Sex</th><th>Age</th><th>Collected</th>
                    <th>Where it is</th><th>WRMD</th><th>VMTH</th>
                </tr>
            </thead>
            <tbody>${data.samples.map(filterRow).join('')}</tbody>
        </table>`;

    // Saying "showing 250 of 812" matters: without it the list looks complete
    // and the download looks wrong.
    note.hidden = data.showing >= data.matched;
    note.textContent =
        `Showing the first ${data.showing.toLocaleString()} of `
        + `${data.matched.toLocaleString()}. The download has all of them.`;
}

function filterRow(sample) {
    const place = [sample.shelf, sample.rack, sample.drawer, sample.box, sample.position]
        .filter(Boolean).join(' › ');
    return `
        <tr>
            <td class="filter-tube">${escapeHtml(sample.tube_id)}</td>
            <td>${escapeHtml(sample.common_name || sample.banding_code || '')}</td>
            <td>${escapeHtml(sample.sample_type || '')}</td>
            <td>${escapeHtml(sample.sex || '')}</td>
            <td>${escapeHtml(sample.age || '')}</td>
            <td>${escapeHtml(sample.collection_date || '')}</td>
            <td class="filter-where">${escapeHtml(place)}</td>
            <td>${escapeHtml(sample.wrmd_number || '')}</td>
            <td>${escapeHtml(sample.vmth_number || '')}</td>
        </tr>`;
}

function downloadFiltered(format) {
    const params = filterParams().toString();
    window.location.href = `/api/export/raptor/${format}${params ? '?' + params : ''}`;
}

function clearBiobankFilter() {
    Object.entries(FILTER_FIELDS).forEach(([field, id]) => {
        filterState[field] = '';
        document.getElementById(id).value = '';
    });
    runBiobankFilter();
}
