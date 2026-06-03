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

/* Split `text` into up to `maxLines` lines, each at most `maxCharsPerLine`
   characters. Prefers breaking at hyphens close to the line limit so an ID
   like "PRV-TBY-001-0626" won't be cut mid-segment. */
function wrapForBradyLabel(text, maxCharsPerLine = 18, maxLines = 3) {
    if (!text) return '';
    const lines = [];
    let rest = String(text);

    while (rest.length > 0 && lines.length < maxLines) {
        if (rest.length <= maxCharsPerLine || lines.length === maxLines - 1) {
            // last allowed line — take up to maxChars and bail
            lines.push(rest.slice(0, maxCharsPerLine));
            rest = rest.slice(maxCharsPerLine);
            break;
        }

        // Find a hyphen near the end of the allowed range to break at
        let breakAt = maxCharsPerLine;
        for (let i = maxCharsPerLine; i >= Math.max(maxCharsPerLine - 5, 1); i--) {
            if (rest[i - 1] === '-') { breakAt = i; break; }
        }

        lines.push(rest.slice(0, breakAt));
        rest = rest.slice(breakAt);
    }

    return lines.join('\n');
}

/* Open a clean popup window with a large Code 128 barcode of `value`,
   intended to be scanned by Brady Express Labels (or any barcode-aware
   label app) on a phone. The encoded value is line-wrapped so Brady
   prints multi-line on a small 30mm Eppendorf label at 8pt. */
function openBradyScanWindow(value) {
    if (!value) {
        showToast('Nothing to encode — sample/tube ID is empty.', 'error');
        return null;
    }
    const wrapped = wrapForBradyLabel(value, 18, 3);
    const lineCount = wrapped.split('\n').length;
    const truncated = wrapped.replace(/\n/g, '').length < String(value).length;

    const w = window.open('', '_blank', 'width=520,height=680');
    if (!w) {
        showToast('Pop-up blocked. Allow pop-ups for this site to use barcode scan.', 'error');
        return null;
    }
    const escapeHtml = s => String(s).replace(/[&<>"']/g, c => (
        {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
    ));
    const originalEsc = escapeHtml(value);
    const wrappedDisplay = escapeHtml(wrapped).replace(/\n/g, '<br>');

    w.document.write(`<!DOCTYPE html><html><head><title>Scan with Brady app</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #ffffff;
    color: #0f172a;
    display: flex; flex-direction: column;
    align-items: center; justify-content: flex-start;
    min-height: 100vh; padding: 24px;
}
h1 { font-size: 0.85rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }
.id { font-size: 1.05rem; color: #0f172a; font-weight: 700; font-family: 'SF Mono', Menlo, monospace; margin-bottom: 8px; word-break: break-all; text-align: center; max-width: 100%; }
.preview {
    background: #f8fafc;
    border: 1px dashed #94a3b8;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 16px;
    font-family: 'SF Mono', Menlo, monospace;
    font-size: 0.9rem;
    line-height: 1.4;
    color: #1e293b;
    text-align: center;
}
.preview-label { font-size: 0.7rem; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; font-family: 'Inter', sans-serif; }
.warn { color: #b45309; font-size: 0.8rem; margin-bottom: 12px; }
.barcode-frame {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 20px 16px;
    margin-bottom: 20px;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    max-width: 100%;
    overflow: hidden;
}
svg { max-width: 100%; height: auto; display: block; }
.help { color: #475569; font-size: 0.9rem; text-align: center; line-height: 1.55; max-width: 380px; margin-top: 4px; }
.help ol { text-align: left; padding-left: 24px; margin-top: 8px; }
.help li { margin-bottom: 4px; }
.help b { color: #0f172a; }
</style>
</head><body>
<h1>Scan with Brady app</h1>
<div class="id">${originalEsc}</div>
<div class="preview">
    <div class="preview-label">Label preview (${lineCount} ${lineCount === 1 ? 'line' : 'lines'})</div>
    ${wrappedDisplay}
</div>
${truncated ? '<div class="warn">⚠ ID too long — truncated to fit 3 lines × 18 chars.</div>' : ''}
<div class="barcode-frame"><svg id="bc"></svg></div>
<div class="help">
    <div>Point your phone camera at the barcode above.</div>
    <ol>
        <li>Open <b>Brady Express Labels</b> on your phone</li>
        <li>Tap the <b>Scan / Barcode</b> icon</li>
        <li>Aim at this screen — the ID will fill in, wrapped to ${lineCount} ${lineCount === 1 ? 'line' : 'lines'}</li>
        <li>Tap <b>Print</b> to send to the M211</li>
    </ol>
</div>
<script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.6/dist/JsBarcode.all.min.js"><\/script>
<script>
    document.addEventListener('DOMContentLoaded', () => {
        try {
            // Use CODE128 auto so JsBarcode picks Set A when needed (newlines)
            JsBarcode("#bc", ${JSON.stringify(wrapped)}, {
                format: "CODE128",
                width: 3,
                height: 130,
                fontSize: 16,
                margin: 10,
                displayValue: false
            });
        } catch (e) {
            document.getElementById('bc').outerHTML =
                '<div style="color:#b91c1c;font-size:0.9rem;text-align:center;">Could not encode this value as a barcode: ' + e.message + '</div>';
        }
    });
<\/script>
</body></html>`);
    w.document.close();
    return w;
}

/* Compact "cryobaby" tube label — sample ID only, max-fit text.
   Sized for Brady M211 0.5" cartridge (M21-500-7425, 203 DPI). */
function generateCliprLabel(sampleId) {
    const canvas = document.createElement('canvas');
    canvas.width = 203;
    canvas.height = 102;
    const ctx = canvas.getContext('2d');

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = '#000000';
    const text = sampleId || 'No ID';

    let fontSize = 16;
    ctx.font = `bold ${fontSize}px Arial, sans-serif`;
    while (ctx.measureText(text).width > 193 && fontSize > 7) {
        fontSize -= 1;
        ctx.font = `bold ${fontSize}px Arial, sans-serif`;
    }
    ctx.fillText(text, 5, Math.round(canvas.height / 2 + fontSize / 2) - 2);

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
