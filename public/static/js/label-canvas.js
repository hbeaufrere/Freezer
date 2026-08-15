/* Label image generation for printing.
   Generates small text-only labels sized for eppendorf tubes. */

function generateRaptorLabel(tubeData) {
    const canvas = document.createElement('canvas');
    // Small label for eppendorf tube (~1" x 0.5" at 203 DPI)
    canvas.width = 203;
    canvas.height = 102;
    const ctx = canvas.getContext('2d');

    // White background
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#000000';

    // Tube ID (bold, largest text)
    ctx.font = 'bold 16px Arial, sans-serif';
    ctx.fillText(tubeData.tube_id || '', 6, 18);

    // WRMD number
    ctx.font = '11px Arial, sans-serif';
    ctx.fillText(tubeData.wrmd_number ? 'WRMD: ' + tubeData.wrmd_number : '', 6, 38);

    // VMTH number
    ctx.fillText(tubeData.vmth_number ? 'VMTH: ' + tubeData.vmth_number : '', 6, 56);

    const img = new Image();
    img.src = canvas.toDataURL('image/png');
    return img;
}

function generateResearchLabel(tubeData, boxLabel) {
    const canvas = document.createElement('canvas');
    canvas.width = 203;
    canvas.height = 102;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#000000';

    ctx.font = 'bold 16px Arial, sans-serif';
    ctx.fillText(tubeData.sample_id || 'No ID', 6, 18);

    ctx.font = '12px Arial, sans-serif';
    ctx.fillText(boxLabel || '', 6, 36);

    if (tubeData.row_pos && tubeData.col_pos) {
        ctx.fillText('Pos: ' + positionLabel(tubeData.row_pos, tubeData.col_pos), 6, 54);
    }

    ctx.font = '11px Arial, sans-serif';
    ctx.fillText(tubeData.date_stored || '', 6, 72);

    const img = new Image();
    img.src = canvas.toDataURL('image/png');
    return img;
}
