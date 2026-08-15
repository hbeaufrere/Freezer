/* Tube label barcodes.

   The M211 has no usable web print path, so the phone does the printing:
   this renders the tube's identifier as a barcode on screen, you scan it with
   Brady Express Labels, and the decoded text lands in the label under the
   Vial preset. Nothing is sent anywhere — the screen is the transfer.

   Two symbologies are offered because different scanner implementations
   accept different things: Code 128 is the classic "scan this text" barcode,
   QR is easier for a phone camera to lock onto at an angle. */

const LABEL_SYMBOLOGY_KEY = 'freezer-label-symbology';

let labelValue = '';

function currentSymbology() {
    try {
        return localStorage.getItem(LABEL_SYMBOLOGY_KEY) || 'code128';
    } catch (e) {
        return 'code128';
    }
}

/* Open the barcode sheet for one tube.
   `value` is what the label will say; `caption` is context for the human. */
function showLabelBarcode(value, caption) {
    labelValue = (value || '').trim();
    if (!labelValue) {
        showToast('This tube has no ID to put on a label yet.', 'warning');
        return;
    }

    document.getElementById('label-value').textContent = labelValue;
    document.getElementById('label-caption').textContent = caption || '';

    setSymbology(currentSymbology());
    bootstrap.Modal.getOrCreateInstance(document.getElementById('labelModal')).show();
}

function setSymbology(kind) {
    try { localStorage.setItem(LABEL_SYMBOLOGY_KEY, kind); } catch (e) { /* private mode */ }

    document.querySelectorAll('[data-symbology]').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.symbology === kind);
    });

    const stage = document.getElementById('label-stage');
    stage.textContent = '';

    if (kind === 'qr') {
        renderQr(stage, labelValue);
    } else {
        renderCode128(stage, labelValue);
    }
}

function renderCode128(stage, value) {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    stage.appendChild(svg);
    JsBarcode(svg, value, {
        format: 'CODE128B',
        width: 2,
        height: 90,
        margin: 14,
        displayValue: false,
        background: '#ffffff',
        lineColor: '#000000',
    });
}

function renderQr(stage, value) {
    // Type 0 auto-sizes to the data; M correction tolerates a little screen glare.
    const qr = qrcode(0, 'M');
    qr.addData(value);
    qr.make();
    stage.innerHTML = qr.createSvgTag({ cellSize: 6, margin: 4 });
    const svg = stage.querySelector('svg');
    if (svg) {
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        svg.style.width = '190px';
        svg.style.height = '190px';
    }
}

function initLabelUI() {
    document.querySelectorAll('[data-symbology]').forEach((btn) => {
        btn.addEventListener('click', () => setSymbology(btn.dataset.symbology));
    });
    attachCopyButton(document.getElementById('btn-copy-label-value'), () => labelValue);
}

document.addEventListener('DOMContentLoaded', initLabelUI);
