/* Freezer visual component — renders shelves, racks, drawers, boxes with occupancy */

async function loadFreezerOverview() {
    try {
        const [freezerData, stats] = await Promise.all([
            API.get('/api/freezer'),
            API.get('/api/stats/freezer')
        ]);

        // Update stat cards
        document.getElementById('stat-total-stored').textContent = stats.total_stored.toLocaleString();
        document.getElementById('stat-capacity').textContent = stats.total_capacity.toLocaleString();
        document.getElementById('stat-raptor').textContent = stats.raptor_count.toLocaleString();
        document.getElementById('stat-research').textContent = stats.research_count.toLocaleString();

        renderFreezer(document.getElementById('freezer-visual'), freezerData);
    } catch (err) {
        console.error('Failed to load freezer:', err);
        document.getElementById('freezer-visual').innerHTML =
            '<div class="alert alert-danger">Failed to load freezer data. Is the server running?</div>';
    }
}

function renderFreezer(container, shelves, options = {}) {
    container.innerHTML = '';
    shelves.forEach(shelf => {
        const shelfEl = document.createElement('div');
        shelfEl.className = 'freezer-shelf';
        shelfEl.dataset.shelfId = shelf.id;

        const section = shelf.section;
        const badgeClass = section === 'raptor' ? 'raptor' : 'research';
        const sectionLabel = section === 'raptor' ? 'Raptor Biobank' : 'Research';

        shelfEl.innerHTML = `
            <div class="shelf-header">
                <span class="shelf-label">${shelf.name}</span>
                <span class="shelf-badge ${badgeClass}">${sectionLabel}</span>
            </div>
            <div class="shelf-racks"></div>
        `;

        const racksContainer = shelfEl.querySelector('.shelf-racks');
        shelf.racks.forEach(rack => {
            const rackEl = createRackElement(rack, options);
            racksContainer.appendChild(rackEl);
        });

        container.appendChild(shelfEl);
    });
}

function createRackElement(rack, options = {}) {
    const rackEl = document.createElement('div');
    rackEl.className = 'rack';
    rackEl.dataset.rackId = rack.id;

    const designationHtml = rack.designation
        ? `<div class="rack-designation">${rack.designation}</div>`
        : '';

    rackEl.innerHTML = `
        <div class="rack-label">${rack.label || 'Rack ' + rack.position}</div>
        ${designationHtml}
        <div class="rack-drawers"></div>
    `;

    const drawersContainer = rackEl.querySelector('.rack-drawers');

    rack.drawers.forEach(drawer => {
        const drawerEl = document.createElement('div');
        drawerEl.className = 'drawer-slot';
        drawerEl.dataset.drawerId = drawer.id;
        drawerEl.title = drawer.label || `Drawer ${drawer.position}`;

        const labelEl = document.createElement('div');
        labelEl.className = 'drawer-label';
        labelEl.textContent = `D${drawer.position}`;
        drawerEl.appendChild(labelEl);

        drawer.boxes.forEach(box => {
            const boxEl = document.createElement('div');
            boxEl.className = 'box-slot ' + getOccupancyClass(box.occupied, box.capacity);
            boxEl.dataset.boxId = box.id;
            boxEl.title = `${box.label}: ${box.occupied}/${box.capacity} tubes`;

            boxEl.addEventListener('click', (e) => {
                e.stopPropagation();
                if (options.onBoxClick) {
                    options.onBoxClick(box.id, box);
                } else {
                    // Default: navigate to section page
                    const section = box.section === 'raptor' ? '/raptor' : '/research';
                    window.location.href = `${section}?box=${box.id}`;
                }
            });

            drawerEl.appendChild(boxEl);
        });

        drawersContainer.appendChild(drawerEl);
    });

    return rackEl;
}

function getOccupancyClass(occupied, capacity) {
    if (!capacity || occupied === 0) return 'empty';
    const pct = occupied / capacity;
    if (pct >= 1) return 'full';
    if (pct >= 0.75) return 'high';
    if (pct >= 0.25) return 'medium';
    return 'low';
}

/* Render a sidebar with racks for a specific section */
async function renderSectionSidebar(containerId, sectionFilter, onBoxClick) {
    const container = document.getElementById(containerId);
    try {
        const shelves = await API.get('/api/freezer');
        container.innerHTML = '';

        const filtered = sectionFilter === 'raptor'
            ? shelves.filter(s => s.section === 'raptor')
            : shelves.filter(s => s.section === 'research');

        if (filtered.length === 0) {
            container.innerHTML = '<div class="text-muted">No shelves assigned to this section.</div>';
            return;
        }

        filtered.forEach(shelf => {
            const shelfTitle = document.createElement('div');
            shelfTitle.className = 'fw-bold text-muted small mb-1 mt-2';
            shelfTitle.textContent = shelf.name;
            container.appendChild(shelfTitle);

            shelf.racks.forEach(rack => {
                const rackEl = createRackElement(rack, { onBoxClick });
                rackEl.classList.add('mb-2');
                container.appendChild(rackEl);
            });
        });

        return shelves;
    } catch (err) {
        container.innerHTML = '<div class="alert alert-danger">Failed to load racks.</div>';
        throw err;
    }
}
