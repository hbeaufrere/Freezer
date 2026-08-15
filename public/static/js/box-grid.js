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

function renderBoxGrid(container, boxData, options = {}) {
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
                    cell.title = `${tube.tube_id}\n${tube.common_name}\nPosition ${position}`;
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

function headerCell(text) {
    const el = document.createElement('div');
    el.className = 'grid-header-cell';
    el.textContent = text;
    return el;
}
