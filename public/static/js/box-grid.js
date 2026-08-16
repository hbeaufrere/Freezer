/* Box grid: one clickable well per tube position. */

/* A 34px circle cannot hold "RTHA26001", so cells show the shortest string
   that still identifies the tube within its box. Colour carries the species,
   the legend decodes the colour, and the full ID is in the tooltip. */
function raptorCellText(tube) {
    const match = (tube.tube_id || '').match(/^[A-Z]{4}\d{2}(.+)$/);
    return {
        code: tube.banding_code || '',
        seq: match ? match[1] : (tube.tube_id || ''),
    };
}

/* Lab sample IDs usually end in the part that distinguishes them
   ("CLIPR-2026-042"), and the leading segments repeat across the whole box.
   Show only the tail; the full ID is in the tooltip. */
function researchCellText(tube) {
    const id = (tube.sample_id || '').trim();
    if (!id) return { code: '—', seq: '' };

    const parts = id.split(/[-_/]/).filter(Boolean);
    const tail = parts.length > 1 ? parts[parts.length - 1] : id;
    return tail.length > 6
        ? { code: tail.slice(0, 6), seq: tail.slice(6, 12) }
        : { code: tail, seq: '' };
}

/* Where this box sits in its drawer, said plainly. "B1" is a name, not a
   direction, and someone standing at an open drawer needs the direction. */
function depthBadge(boxData) {
    const where = depthLabel(boxData.position, boxData.drawer_box_count);
    if (!where) return '';
    const front = boxData.position === 1;
    return `<span class="depth-badge${front ? ' is-front' : ''}">
        <i class="bi bi-box-arrow-in-down-left"></i>${escapeHtml(where)}</span>`;
}

function renderBoxGrid(container, boxData, options = {}) {
    if (boxData.box_type === 'plain') {
        renderPlainBox(container, boxData, options);
        return null;
    }

    const rows = boxData.grid_rows || 10;
    const cols = boxData.grid_cols || 10;
    const tubes = boxData.tubes || [];
    const isRaptor = boxData.section === 'raptor';

    const tubeMap = new Map();
    const speciesIndexMap = {};
    let nextSpeciesIndex = 0;

    tubes.forEach((tube) => {
        tubeMap.set(`${tube.row_pos},${tube.col_pos}`, tube);
        if (isRaptor && tube.banding_code && !(tube.banding_code in speciesIndexMap)) {
            speciesIndexMap[tube.banding_code] = nextSpeciesIndex++;
        }
    });

    const shell = document.createElement('div');
    shell.className = 'box-grid-shell';
    shell.innerHTML = `
        <div class="box-grid-head">
            <span class="box-grid-title">${escapeHtml(boxData.label || 'Box')}</span>
            ${depthBadge(boxData)}
            <span class="box-grid-count">${tubes.length} / ${rows * cols} positions filled</span>
        </div>
        <div class="box-grid-scroll"></div>`;

    const grid = document.createElement('div');
    grid.className = 'box-grid';
    grid.style.gridTemplateColumns = `32px repeat(${cols}, minmax(34px, 1fr))`;

    // Header row: blank corner, then column numbers.
    grid.appendChild(headerCell(''));
    for (let c = 1; c <= cols; c++) grid.appendChild(headerCell(c));

    for (let r = 1; r <= rows; r++) {
        grid.appendChild(headerCell(ROW_LABELS[r - 1] || String.fromCharCode(64 + r)));

        for (let c = 1; c <= cols; c++) {
            const tube = tubeMap.get(`${r},${c}`);
            const cell = document.createElement('button');
            cell.type = 'button';
            const position = positionLabel(r, c);

            if (tube) {
                const parts = isRaptor ? raptorCellText(tube) : researchCellText(tube);
                cell.className = 'tube-cell filled';

                if (isRaptor) {
                    const index = speciesIndexMap[tube.banding_code] % 12;
                    cell.classList.add(`species-${index}`);
                    cell.title = `${tube.tube_id}\n${tube.common_name}`
                        + `\n${tube.sample_type || 'Plasma'}\nPosition ${position}`;
                    cell.setAttribute('aria-label', `${tube.tube_id}, ${tube.common_name}, position ${position}`);
                } else {
                    cell.classList.add('research');
                    const label = tube.sample_id || 'Untitled sample';
                    cell.title = `${label}\nPosition ${position}`;
                    cell.setAttribute('aria-label', `${label}, position ${position}`);
                }

                cell.innerHTML =
                    `<span class="cell-code">${escapeHtml(parts.code)}</span>` +
                    (parts.seq ? `<span class="cell-seq">${escapeHtml(parts.seq)}</span>` : '');

                cell.addEventListener('click', () => options.onTubeClick?.(tube, r, c));
            } else {
                cell.className = 'tube-cell empty';
                cell.title = `Position ${position} — empty`;
                cell.setAttribute('aria-label', `Empty position ${position}, add a tube`);
                cell.addEventListener('click', () => options.onEmptyClick?.(r, c));
            }

            grid.appendChild(cell);
        }
    }

    shell.querySelector('.box-grid-scroll').appendChild(grid);
    container.textContent = '';
    container.appendChild(shell);

    return isRaptor ? { speciesIndexMap, tubes } : null;
}

/* A plain box: contents as a list, because there are no wells to draw.

   The grid earns its space by answering "what is in C7". A box of whirl-paks
   has no C7, so the same question becomes "what is in here", and a list
   answers that better than a hundred identical circles would. */
function renderPlainBox(container, boxData, options = {}) {
    const tubes = boxData.tubes || [];
    const capacity = boxData.capacity || (boxData.grid_rows || 10) * (boxData.grid_cols || 10);

    const shell = document.createElement('div');
    shell.className = 'box-grid-shell plain-box';
    shell.innerHTML = `
        <div class="box-grid-head">
            <span class="box-grid-title">${escapeHtml(boxData.label || 'Box')}</span>
            ${depthBadge(boxData)}
            <span class="box-grid-count">${tubes.length} of ${capacity} stored</span>
        </div>
        <div class="plain-list"></div>`;

    const list = shell.querySelector('.plain-list');

    if (!tubes.length) {
        list.innerHTML = `
            <div class="empty-state py-4">
                <i class="bi bi-bag empty-icon"></i>
                <div class="empty-title">Nothing in this box yet</div>
                <div class="empty-hint">Samples here are listed rather than placed in wells.</div>
            </div>`;
    }

    tubes.forEach((tube) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'plain-item';
        item.innerHTML = `
            <span class="plain-item-id">${escapeHtml(tube.sample_id || 'Untitled sample')}</span>
            <span class="plain-item-meta">
                ${tube.description ? escapeHtml(tube.description) : '<em>No description</em>'}
            </span>
            <span class="plain-item-side">
                ${tube.date_stored ? escapeHtml(tube.date_stored) : ''}
                ${tube.freeze_thaw_cycles
                    ? `<span class="plain-item-ft" title="Freeze-thaw cycles">
                           <i class="bi bi-thermometer-half"></i>${tube.freeze_thaw_cycles}</span>`
                    : ''}
            </span>`;
        item.addEventListener('click', () => options.onTubeClick?.(tube, null, null));
        list.appendChild(item);
    });

    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'btn btn-primary plain-add';
    add.disabled = tubes.length >= capacity;
    add.innerHTML = tubes.length >= capacity
        ? '<i class="bi bi-x-circle me-1"></i>Box is full'
        : '<i class="bi bi-plus-lg me-1"></i>Add a sample';
    add.addEventListener('click', () => options.onEmptyClick?.(null, null));
    list.appendChild(add);

    container.textContent = '';
    container.appendChild(shell);
}

function headerCell(text) {
    const el = document.createElement('div');
    el.className = 'grid-header-cell';
    el.textContent = text;
    return el;
}
