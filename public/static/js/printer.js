/* Brady M211 label printing.

   Two paths, in order of preference:
   1. Web Bluetooth (Chrome/Edge) when the Brady Web SDK is present on the page.
   2. The browser print dialog, which works in every browser.

   The SDK is not bundled with this app, so path 2 is what runs today. The
   Bluetooth hooks stay in place for whenever the SDK is added. */

let printerDevice = null;
const bleSupported = Boolean(navigator.bluetooth);
const bradyReady = () => Boolean(window.BradySdk && window.bradySdkInstance);

function initPrinterUI() {
    const btn = document.getElementById('btn-printer-connect');
    if (!btn) return;

    const icon = document.getElementById('printer-icon');

    if (bleSupported) {
        btn.title = 'Connect a Brady M211 over Bluetooth';
        btn.addEventListener('click', connectPrinter);
    } else {
        if (icon) icon.className = 'bi bi-printer';
        btn.title = 'Labels open in a print preview (Bluetooth needs Chrome or Edge)';
        btn.addEventListener('click', () => showToast(
            'This browser has no Bluetooth support. Labels will open in a print preview instead.',
            'warning'
        ));
    }
}

async function connectPrinter() {
    const btn = document.getElementById('btn-printer-connect');
    const icon = document.getElementById('printer-icon');

    if (!bleSupported) {
        showToast('Bluetooth is not available in this browser.', 'warning');
        return false;
    }

    try {
        printerDevice = await navigator.bluetooth.requestDevice({
            filters: [{ namePrefix: 'M211' }],
            optionalServices: ['00001101-0000-1000-8000-00805f9b34fb'],
        });

        btn.classList.add('is-on');
        btn.title = `Connected: ${printerDevice.name || 'M211'}`;
        if (icon) icon.className = 'bi bi-bluetooth';

        printerDevice.addEventListener('gattserverdisconnected', () => {
            printerDevice = null;
            btn.classList.remove('is-on');
            btn.title = 'Connect a Brady M211 over Bluetooth';
        });

        showToast(`Printer connected: ${printerDevice.name || 'M211'}`);
        return true;
    } catch (err) {
        btn.classList.remove('is-on');
        // NotFoundError just means the user closed the picker.
        if (err.name !== 'NotFoundError') {
            showToast('Could not connect to the printer: ' + err.message, 'error');
        }
        return false;
    }
}

async function printLabel(imgElement) {
    if (printerDevice && bradyReady()) {
        try {
            await window.bradySdkInstance.printBitmap(imgElement, 0.1, 0);
            showToast('Label sent to the printer');
            return;
        } catch (err) {
            showToast('Bluetooth printing failed — opening a print preview.', 'warning');
        }
    }
    printViaDialog(imgElement);
}

function printViaDialog(imgElement) {
    const win = window.open('', '_blank', 'width=520,height=420');
    if (!win) {
        showToast('Allow pop-ups for this site to print labels.', 'error');
        return;
    }

    win.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Print label</title><style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;display:flex;
       flex-direction:column;align-items:center;justify-content:center;
       min-height:100vh;padding:24px;background:#eef2f3;color:#0f1a1d}
  .preview{border:1px dashed #bcc9cc;border-radius:10px;padding:18px;
           background:#fff;margin-bottom:18px}
  .preview img{display:block;image-rendering:pixelated}
  button{padding:10px 30px;font-size:15px;background:#0e6c76;color:#fff;
         border:none;border-radius:8px;cursor:pointer;font-weight:600}
  button:hover{background:#0a545c}
  .hint{margin-top:12px;color:#61757b;font-size:13px;text-align:center}
  @media print{
    @page{margin:0;size:1in 0.5in}
    body{padding:0;background:#fff;min-height:auto;display:block}
    .preview{border:none;padding:0;margin:0}
    button,.hint{display:none}
  }
</style></head><body>
  <div class="preview"><img src="${imgElement.src}" alt="Tube label"></div>
  <button onclick="window.print()">Print label</button>
  <div class="hint">Choose the Brady M211 in the print dialog</div>
  <script>setTimeout(function(){window.print();},400);<\/script>
</body></html>`);
    win.document.close();
}

document.addEventListener('DOMContentLoaded', initPrinterUI);
