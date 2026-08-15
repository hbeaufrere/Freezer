/* Freezer visual: shelves, racks, drawers and box slots with occupancy shading. */

async function loadFreezerOverview() {
    const container = document.getElementById('freezer-visual');
    try {
        const [shelves, stats] = await Promise.all([
            API.get('/api/freezer'),
            API.get('/api/stats/freezer'),
        ]);

        setText('stat-total-stored', stats.tubes_stored.toLocaleString());
        setText('stat-capacity', stats.total_capacity.toLocaleString());
        setText('stat-raptor', stats.raptor_count.toLocaleString());
        setText('stat-research', stats.research_count.toLocaleString());
        setText('stat-percent', `${stats.percent_full}% of capacity`);
        setText('stat-boxes', `${stats.total_boxes} boxes`);

        renderFreezer(container, shelves, { percentFull: stats.percent_full });
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-exclamation-triangle empty-icon"></i>
                <div class="empty-title">Could not load the freezer</div>
                <div class="empty-hint">${escapeHtml(err.message)}</div>
            </div>`;
    }
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function renderFreezer(container, shelves, options = {}) {
    container.textContent = '';

    const plate = document.createElement('div');
    plate.className = 'cabinet-plate';
    plate.innerHTML = `
        <span class="cabinet-model">Eppendorf CryoCube F740hi</span>
        <span class="cabinet-temp">&minus;80 &deg;C</span>
        <span class="cabinet-fill">${options.percentFull ?? 0}% full</span>`;
    container.appendChild(plate);

    shelves.forEach((shelf) => {
        const stored = shelfOccupancy(shelf);

        const shelfEl = document.createElement('section');
        shelfEl.className = 'freezer-shelf';
        shelfEl.dataset.shelfId = shelf.id;

        const isRaptor = shelf.section === 'raptor';
        shelfEl.innerHTML = `
            <header class="shelf-header">
                <span class="shelf-label">${escapeHtml(shelf.name)}</span>
                <span class="d-flex align-items-center gap-2">
                    <span class="shelf-meta">${stored.occupied} / ${stored.capacity}</span>
                    <span class="shelf-badge ${isRaptor ? 'raptor' : 'research'}">
                        ${isRaptor ? 'Raptor biobank' : 'Research'}
                    </span>
                </span>
            </header>
            <div class="shelf-racks"></div>`;

        const racks = shelfEl.querySelector('.shelf-racks');
        shelf.racks.forEach((rack) => racks.appendChild(createRackElement(rack, options)));
        container.appendChild(shelfEl);
    });
}

function shelfOccupancy(shelf) {
    let occupied = 0;
    let capacity = 0;
    shelf.racks.forEach((rack) =>
        rack.drawers.forEach((drawer) =>
            drawer.boxes.forEach((box) => {
                occupied += box.occupied;
                capacity += box.capacity;
            })));
    return { occupied, capacity };
}

function createRackElement(rack, options = {}) {
    const rackEl = document.createElement('div');
    rackEl.className = 'rack';
    rackEl.dataset.rackId = rack.id;

    rackEl.innerHTML = `
        <div class="rack-label">${escapeHtml(rack.label || 'Rack ' + rack.position)}</div>
        ${rack.designation
            ? `<div class="rack-designation" title="${escapeHtml(rack.designation)}">${escapeHtml(rack.designation)}</div>`
            : ''}
        <div class="rack-drawers"></div>`;

    const drawers = rackEl.querySelector('.rack-drawers');

    rack.drawers.forEach((drawer) => {
        const drawerEl = document.createElement('div');
        drawerEl.className = 'drawer-slot';

        const label = document.createElement('span');
        label.className = 'drawer-label';
        label.textContent = `D${drawer.position}`;
        label.title = drawer.label || `Drawer ${drawer.position}`;
        drawerEl.appendChild(label);

        const boxWrap = document.createElement('span');
        boxWrap.className = 'drawer-boxes';
        drawerEl.appendChild(boxWrap);

        drawer.boxes.forEach((box) => {
            const pct = box.capacity ? Math.round((box.occupied / box.capacity) * 100) : 0;

            // Buttons rather than divs, so the grid is reachable by keyboard.
            const boxEl = document.createElement('button');
            boxEl.type = 'button';
            boxEl.className = `box-slot ${occupancyClass(box.occupied, box.capacity)}`;
            boxEl.dataset.boxId = box.id;
            boxEl.title = `${box.label}\n${box.occupied} of ${box.capacity} positions (${pct}%)`;
            boxEl.setAttribute('aria-label', `Box ${box.label}, ${box.occupied} of ${box.capacity} filled`);

            boxEl.addEventListener('click', (event) => {
                event.stopPropagation();
                if (options.onBoxClick) {
                    options.onBoxClick(box.id, box);
                } else {
                    const page = box.section === 'raptor' ? '/raptor' : '/research';
                    window.location.href = `${page}?box=${box.id}`;
                }
            });

            boxWrap.appendChild(boxEl);
        });

        // The line the lab writes on the drawer: experiment, species, project.
        if (options.editableNotes) {
            drawerEl.appendChild(drawerNoteInput(drawer));
        } else if (drawer.note) {
            const note = document.createElement('span');
            note.className = 'drawer-note-static';
            note.textContent = drawer.note;
            note.title = drawer.note;
            drawerEl.appendChild(note);
        }

        drawers.appendChild(drawerEl);
    });

    return rackEl;
}

function drawerNoteInput(drawer) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'drawer-note';
    input.value = drawer.note || '';
    input.placeholder = 'Notes…';
    input.maxLength = 200;
    input.setAttribute('aria-label', `Note for drawer ${drawer.label || drawer.position}`);

    let saved = drawer.note || '';

    async function commit() {
        const value = input.value.trim();
        if (value === saved) return;
        try {
            await API.put(`/api/drawers/${drawer.id}`, { note: value });
            saved = value;
            drawer.note = value;
            input.classList.add('is-saved');
            setTimeout(() => input.classList.remove('is-saved'), 900);
        } catch (err) {
            input.value = saved;
            showToast(err.message, 'error');
        }
    }

    // Save on blur rather than per keystroke, so typing is not a write storm.
    input.addEventListener('blur', commit);
    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') { event.preventDefault(); input.blur(); }
        if (event.key === 'Escape') { input.value = saved; input.blur(); }
    });
    // Clicking into the note must not also open a box.
    input.addEventListener('click', (event) => event.stopPropagation());

    return input;
}

/* Occupancy reads as a quantity: one hue, six steps from empty to full. */
function occupancyClass(occupied, capacity) {
    if (!capacity || occupied === 0) return 'occ-0';
    const pct = occupied / capacity;
    if (pct >= 1) return 'occ-5';
    if (pct >= 0.75) return 'occ-4';
    if (pct >= 0.5) return 'occ-3';
    if (pct >= 0.25) return 'occ-2';
    return 'occ-1';
}

/* Sidebar listing every rack in one section, used by the two section pages. */
async function renderSectionSidebar(containerId, section, onBoxClick) {
    const container = document.getElementById(containerId);
    try {
        const shelves = await API.get('/api/freezer');
        const matching = shelves.filter((s) => s.section === section);

        container.textContent = '';

        if (!matching.length) {
            container.innerHTML =
                '<div class="empty-state py-4"><div class="empty-hint">No shelves in this section.</div></div>';
            return shelves;
        }

        matching.forEach((shelf) => {
            const heading = document.createElement('div');
            heading.className = 'sidebar-heading';
            heading.textContent = shelf.name;
            container.appendChild(heading);

            shelf.racks.forEach((rack) =>
                container.appendChild(
                    createRackElement(rack, { onBoxClick, editableNotes: true })));
        });

        return shelves;
    } catch (err) {
        container.innerHTML = `
            <div class="empty-state py-4">
                <div class="empty-title">Could not load racks</div>
                <div class="empty-hint">${escapeHtml(err.message)}</div>
            </div>`;
        throw err;
    }
}
