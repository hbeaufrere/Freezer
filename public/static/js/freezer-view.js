/* Freezer visual: shelves, racks, drawers and box slots with occupancy shading. */

async function loadFreezerOverview() {
    const container = document.getElementById('freezer-visual');
    try {
        const [shelves, stats, sites, mail] = await Promise.all([
            API.get('/api/freezer'),
            API.get('/api/stats/freezer'),
            API.get('/api/collection-sites').catch(() => []),
            API.get('/api/notifications').catch(() => ({ configured: false })),
        ]);

        setText('stat-total-stored', stats.tubes_stored.toLocaleString());
        setText('stat-capacity', stats.total_capacity.toLocaleString());
        setText('stat-raptor', stats.raptor_count.toLocaleString());
        setText('stat-research', stats.research_count.toLocaleString());
        setText('stat-percent', `${stats.percent_full}% of capacity`);
        setText('stat-boxes', `${stats.total_boxes} boxes`);

        renderFreezer(container, shelves, {
            percentFull: stats.percent_full,
            collectionSites: sites,
            mail,
        });
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
        <span class="cabinet-orient"
              title="Drawers stack downwards, so D1 is the top drawer. Boxes sit one behind another inside a drawer, so B1 is the one at the front.">
            <i class="bi bi-box-arrow-in-down-left"></i>D1 is the top drawer &middot; B1 is the front box
        </span>
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

        // Samples waiting in the satellite freezers belong with the raptor
        // shelf: that is where they are headed.
        if (isRaptor && options.collectionSites) {
            shelfEl.appendChild(renderCollectionPanel(options.collectionSites, options.mail));
        }

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

    // Column numbers over the box strip. Without them the four rectangles are
    // anonymous, and B3 is only discoverable by hovering.
    const widest = Math.max(0, ...rack.drawers.map((d) => d.boxes.length));
    if (widest) {
        const axis = document.createElement('div');
        axis.className = 'drawer-axis';
        axis.setAttribute('aria-hidden', 'true');
        // A spacer of its own rather than an empty .drawer-label: that class
        // means "this drawer's name", and anything selecting it should not
        // have to skip a decoration first.
        axis.innerHTML =
            '<span class="axis-spacer"></span><span class="drawer-boxes">'
            + Array.from({ length: widest }, (_, i) =>
                `<span class="axis-cell${i === 0 ? ' is-front' : ''}">${i + 1}</span>`).join('')
            + '</span>';
        drawers.appendChild(axis);
    }

    rack.drawers.forEach((drawer) => {
        const drawerEl = document.createElement('div');
        drawerEl.className = 'drawer-slot';

        const label = document.createElement('span');
        label.className = 'drawer-label';
        label.textContent = `D${drawer.position}`;
        // Drawers stack, so the screen already puts D1 where it belongs. The
        // tooltip only has to name the ends.
        label.title = `${drawer.label || `Drawer ${drawer.position}`}`
            + (drawer.position === 1 ? ' — top drawer' : '')
            + (drawer.position === rack.drawers.length ? ' — bottom drawer' : '');
        drawerEl.appendChild(label);

        const boxWrap = document.createElement('span');
        boxWrap.className = 'drawer-boxes';
        drawerEl.appendChild(boxWrap);

        drawer.boxes.forEach((box) => {
            const pct = box.capacity ? Math.round((box.occupied / box.capacity) * 100) : 0;

            // Buttons rather than divs, so the grid is reachable by keyboard.
            // A plain box holds samples rather than filling positions, so it
            // is described — and outlined — differently.
            const isPlain = box.box_type === 'plain';
            const unit = isPlain ? 'samples' : 'positions';

            const depth = depthLabel(box.position, drawer.boxes.length);

            const boxEl = document.createElement('button');
            boxEl.type = 'button';
            boxEl.className = `box-slot ${occupancyClass(box.occupied, box.capacity)}`
                + (isPlain ? ' is-plain' : '')
                + (box.position === 1 ? ' is-front' : '');
            boxEl.dataset.boxId = box.id;
            boxEl.title = `${box.label}${isPlain ? ' (plain box)' : ''}`
                + `\n${depth}`
                + `\n${box.occupied} of ${box.capacity} ${unit} (${pct}%)`;
            boxEl.setAttribute('aria-label',
                `Box ${box.label}, ${depth}, ${box.occupied} of ${box.capacity} ${unit} filled`);

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

/* ---- Samples waiting at the satellite freezers ------------- */

/* How urgent a backlog is, by the age of its oldest drop. Plasma left in an
   ordinary freezer degrades, so age matters more than count. */
function backlogClass(days) {
    if (days === null || days === undefined) return '';
    if (days >= 30) return 'is-overdue';
    if (days >= 14) return 'is-ageing';
    return '';
}

function renderCollectionPanel(sites, mail) {
    const panel = document.createElement('div');
    panel.className = 'collect-panel';

    const total = sites.reduce((sum, s) => sum + (s.pending_samples || 0), 0);

    panel.innerHTML = `
        <div class="collect-head">
            <span class="collect-title">
                <i class="bi bi-inboxes me-1"></i>Samples to collect
            </span>
            <span class="d-flex align-items-center gap-2">
                <span class="shelf-meta">${total} waiting</span>
                ${mail && mail.configured
                    ? `<button type="button" class="copy-btn collect-bell"
                               title="Email alerts go to ${escapeHtml(mail.recipient)} — click to send a test"
                               aria-label="Send a test notification email">
                           <i class="bi bi-bell"></i>
                       </button>`
                    : ''}
            </span>
        </div>
        <div class="collect-sites"></div>`;

    const bell = panel.querySelector('.collect-bell');
    if (bell) bell.addEventListener('click', () => sendTestEmail(bell));

    const list = panel.querySelector('.collect-sites');

    sites.forEach((site) => {
        const waiting = site.pending_samples || 0;
        const days = site.oldest_age_days;

        const card = document.createElement('div');
        card.className = `collect-site ${waiting ? backlogClass(days) : 'is-empty'}`;
        card.innerHTML = `
            <div class="collect-site-head">
                <span class="collect-code">${escapeHtml(site.code)}</span>
                <button type="button" class="copy-btn collect-qr" title="Show the QR code"
                        aria-label="Show the drop-off QR code for ${escapeHtml(site.code)}">
                    <i class="bi bi-qr-code"></i>
                </button>
            </div>
            <div class="collect-count">${waiting}</div>
            <div class="collect-age">${
                waiting
                    ? `oldest ${days ?? 0} day${days === 1 ? '' : 's'}`
                    : 'nothing waiting'
            }</div>`;

        const collect = document.createElement('button');
        collect.type = 'button';
        collect.className = 'btn btn-sm btn-outline-secondary w-100 mt-2';
        collect.textContent = 'Mark collected';
        collect.disabled = !waiting;
        collect.addEventListener('click', () => markCollected(site));
        card.appendChild(collect);

        card.querySelector('.collect-qr')
            .addEventListener('click', () => showSiteQr(site));

        list.appendChild(card);
    });

    return panel;
}

/* Checking the mail settings should not require standing at a freezer. */
async function sendTestEmail(button) {
    const icon = button.querySelector('i');
    button.disabled = true;
    icon.className = 'bi bi-hourglass-split';
    try {
        await API.post('/api/notifications/test', {});
        icon.className = 'bi bi-check-lg';
        showToast('Test email sent — check your inbox.');
    } catch (err) {
        icon.className = 'bi bi-bell';
        showToast(err.message, 'error');
    } finally {
        button.disabled = false;
        setTimeout(() => { icon.className = 'bi bi-bell'; }, 2000);
    }
}

async function markCollected(site) {
    const waiting = site.pending_samples || 0;
    if (!confirm(`Mark ${waiting} sample(s) at ${site.code} as collected?`)) return;

    try {
        const who = (localStorage.getItem('freezer-retrieved-by') || '').trim();
        const result = await API.post(`/api/collection-sites/${site.id}/collect`,
                                      who ? { collected_by: who } : {});
        showToast(`${result.collected_samples} sample(s) collected from ${site.code}`);
        loadFreezerOverview();
    } catch (err) {
        showToast(err.message, 'error');
    }
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
