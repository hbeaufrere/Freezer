/* Box grid component — renders 9x9 or 10x10 tube grid */

function renderBoxGrid(container, boxData, options = {}) {
    const { grid_rows, grid_cols, tubes, section } = boxData;
    const rows = grid_rows || 9;
    const cols = grid_cols || 9;

    // Build tube lookup: "row,col" -> tube data
    const tubeMap = {};
    const speciesIndexMap = {};
    let speciesCounter = 0;

    (tubes || []).forEach(tube => {
        const key = `${tube.row_pos},${tube.col_pos}`;
        tubeMap[key] = tube;
        // Track species for color coding
        if (section === 'raptor' && tube.banding_code) {
            if (!(tube.banding_code in speciesIndexMap)) {
                speciesIndexMap[tube.banding_code] = speciesCounter++;
            }
        }
    });

    // Create grid
    const grid = document.createElement('div');
    grid.className = 'box-grid';
    grid.style.gridTemplateColumns = `40px repeat(${cols}, 1fr)`;

    // Header row: empty corner + column numbers
    const corner = document.createElement('div');
    corner.className = 'grid-header-cell';
    grid.appendChild(corner);

    for (let c = 1; c <= cols; c++) {
        const header = document.createElement('div');
        header.className = 'grid-header-cell';
        header.textContent = c;
        grid.appendChild(header);
    }

    // Data rows
    for (let r = 1; r <= rows; r++) {
        // Row header (letter)
        const rowHeader = document.createElement('div');
        rowHeader.className = 'grid-header-cell';
        rowHeader.textContent = String.fromCharCode(64 + r);
        grid.appendChild(rowHeader);

        for (let c = 1; c <= cols; c++) {
            const cell = document.createElement('div');
            const key = `${r},${c}`;
            const tube = tubeMap[key];

            if (tube) {
                cell.className = 'tube-cell filled';
                if (section === 'raptor' && tube.banding_code) {
                    const idx = speciesIndexMap[tube.banding_code] % 12;
                    cell.classList.add(`species-${idx}`);
                    cell.textContent = tube.tube_id || tube.banding_code;
                    cell.title = `${tube.tube_id} - ${tube.common_name}\n${positionLabel(r, c)}`;
                } else {
                    cell.textContent = tube.sample_id || '?';
                    cell.title = `${tube.sample_id || 'No ID'}\n${positionLabel(r, c)}`;
                }
                cell.addEventListener('click', () => {
                    if (options.onTubeClick) options.onTubeClick(tube, r, c);
                });
            } else {
                cell.className = 'tube-cell empty';
                cell.addEventListener('click', () => {
                    if (options.onEmptyClick) options.onEmptyClick(r, c);
                });
            }

            grid.appendChild(cell);
        }
    }

    container.innerHTML = '';
    container.appendChild(grid);

    // Return species legend data for raptor section
    if (section === 'raptor') {
        return { speciesIndexMap, tubes: tubes || [] };
    }
    return null;
}
