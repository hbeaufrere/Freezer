/* Label image generation for printing.
   Generates label images on an HTML5 Canvas.
   Labels include a QR code (tube ID) and text fields. */

function generateRaptorLabel(tubeData) {
    const canvas = document.createElement('canvas');
    // Label dimensions for Brady M211 at 203 DPI
    // ~1.5" x 0.75" = 305 x 152 pixels
    canvas.width = 305;
    canvas.height = 152;
    const ctx = canvas.getContext('2d');

    // White background
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw QR code (simple text-based representation if no QR library)
    drawSimpleQR(ctx, tubeData.tube_id || '', 8, 8, 80);

    // Text content
    ctx.fillStyle = '#000000';

    // Tube ID (large, bold)
    ctx.font = 'bold 22px Arial, sans-serif';
    ctx.fillText(tubeData.tube_id || '', 100, 30);

    // Species common name
    ctx.font = '14px Arial, sans-serif';
    ctx.fillText(tubeData.common_name || '', 100, 52);

    // Scientific name (italic)
    ctx.font = 'italic 12px Arial, sans-serif';
    ctx.fillText(tubeData.scientific_name || '', 100, 70);

    // Collection date
    ctx.font = '12px Arial, sans-serif';
    ctx.fillText(tubeData.collection_date || '', 100, 90);

    // WRMD number
    if (tubeData.wrmd_number) {
        ctx.font = '11px Arial, sans-serif';
        ctx.fillText('WRMD: ' + tubeData.wrmd_number, 100, 108);
    }

    // VMTH number
    if (tubeData.vmth_number) {
        ctx.font = '11px Arial, sans-serif';
        ctx.fillText('VMTH: ' + tubeData.vmth_number, 100, 124);
    }

    // Freeze-thaw cycles
    ctx.font = '10px Arial, sans-serif';
    ctx.fillText('F/T: ' + (tubeData.freeze_thaw_cycles || 0), 100, 142);

    const img = new Image();
    img.src = canvas.toDataURL('image/png');
    return img;
}

function generateResearchLabel(tubeData, boxLabel) {
    const canvas = document.createElement('canvas');
    canvas.width = 305;
    canvas.height = 152;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    drawSimpleQR(ctx, tubeData.sample_id || '', 8, 8, 80);

    ctx.fillStyle = '#000000';

    ctx.font = 'bold 22px Arial, sans-serif';
    ctx.fillText(tubeData.sample_id || 'No ID', 100, 35);

    ctx.font = '14px Arial, sans-serif';
    ctx.fillText(boxLabel || '', 100, 60);

    if (tubeData.row_pos && tubeData.col_pos) {
        ctx.fillText('Pos: ' + positionLabel(tubeData.row_pos, tubeData.col_pos), 100, 82);
    }

    ctx.font = '12px Arial, sans-serif';
    ctx.fillText(tubeData.date_stored || '', 100, 104);

    const img = new Image();
    img.src = canvas.toDataURL('image/png');
    return img;
}

/**
 * Simple QR-like code drawn on canvas.
 * For production use, integrate a proper QR library like qrcode-generator.
 * This draws a simple data matrix pattern as a placeholder.
 */
function drawSimpleQR(ctx, data, x, y, size) {
    if (!data) return;

    const modules = 21; // QR version 1 is 21x21
    const cellSize = size / modules;

    // Generate a deterministic pattern from the data string
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
        hash = ((hash << 5) - hash) + data.charCodeAt(i);
        hash |= 0;
    }

    ctx.fillStyle = '#000000';

    // Draw finder patterns (3 corners)
    drawFinderPattern(ctx, x, y, cellSize);
    drawFinderPattern(ctx, x + (modules - 7) * cellSize, y, cellSize);
    drawFinderPattern(ctx, x, y + (modules - 7) * cellSize, cellSize);

    // Fill data area with deterministic pattern
    let seed = Math.abs(hash);
    for (let r = 0; r < modules; r++) {
        for (let c = 0; c < modules; c++) {
            // Skip finder pattern areas
            if ((r < 8 && c < 8) || (r < 8 && c > modules - 9) || (r > modules - 9 && c < 8)) continue;

            seed = (seed * 1103515245 + 12345) & 0x7fffffff;
            if (seed % 3 === 0) {
                ctx.fillRect(x + c * cellSize, y + r * cellSize, cellSize, cellSize);
            }
        }
    }

    // Encode actual data chars as visible dots in a dedicated zone
    ctx.fillStyle = '#000000';
    for (let i = 0; i < Math.min(data.length, 10); i++) {
        const code = data.charCodeAt(i);
        const row = 9 + Math.floor(i / 5);
        const col = 9 + (i % 5) * 2;
        if (row < modules && col < modules) {
            ctx.fillRect(x + col * cellSize, y + row * cellSize, cellSize * 1.5, cellSize * 1.5);
        }
    }
}

function drawFinderPattern(ctx, x, y, cellSize) {
    const s = cellSize;
    // Outer border (7x7)
    ctx.fillStyle = '#000000';
    ctx.fillRect(x, y, s * 7, s * 7);
    // Inner white (5x5)
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(x + s, y + s, s * 5, s * 5);
    // Center black (3x3)
    ctx.fillStyle = '#000000';
    ctx.fillRect(x + s * 2, y + s * 2, s * 3, s * 3);
}
