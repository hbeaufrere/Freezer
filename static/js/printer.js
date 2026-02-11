/* Brady M211 Bluetooth label printer integration.
   Three-tier printing strategy:
   1. Web Bluetooth (Chrome/Edge) — direct BLE connection to M211
   2. Browser print dialog (Safari/Firefox/any) — opens label in print preview
   3. Info notification — explains browser limitation */

let printerDevice = null;
const bleSupported = !!(navigator.bluetooth);

function initPrinterUI() {
    const btn = document.getElementById('btn-printer-connect');
    const icon = document.getElementById('printer-icon');
    const statusText = document.getElementById('printer-status-text');

    if (!btn) return;

    if (bleSupported) {
        // Chrome/Edge: show Bluetooth icon, allow direct connection
        icon.className = 'bi bi-bluetooth me-1';
        statusText.textContent = 'Printer';
        btn.addEventListener('click', connectPrinter);
    } else {
        // Safari/Firefox: show print icon, explain fallback
        icon.className = 'bi bi-printer me-1';
        statusText.textContent = 'Print';
        btn.title = 'Labels will open in a print preview (Bluetooth requires Chrome or Edge)';
        btn.addEventListener('click', () => {
            showToast(
                'Direct Bluetooth printing requires Chrome or Edge. ' +
                'When you print a label, it will open in a print preview window instead.',
                'warning'
            );
        });
    }
}

async function connectPrinter() {
    const statusText = document.getElementById('printer-status-text');
    const btn = document.getElementById('btn-printer-connect');

    if (!bleSupported) {
        showToast('Web Bluetooth is not available in this browser. Labels will open in a print preview.', 'warning');
        return false;
    }

    try {
        // Try Brady SDK first if available
        if (window.BradySdk) {
            return await connectViaBradySdk();
        }

        statusText.textContent = 'Scanning...';
        printerDevice = await navigator.bluetooth.requestDevice({
            filters: [{ namePrefix: 'M211' }],
            optionalServices: ['00001101-0000-1000-8000-00805f9b34fb']
        });

        statusText.textContent = 'Connected: ' + (printerDevice.name || 'M211');
        btn.classList.remove('btn-outline-light');
        btn.classList.add('btn-light');
        showToast('Printer connected: ' + (printerDevice.name || 'M211'));
        return true;
    } catch (err) {
        statusText.textContent = 'Printer';
        btn.classList.remove('btn-light');
        btn.classList.add('btn-outline-light');
        if (err.name !== 'NotFoundError') {
            showToast('Printer connection failed: ' + err.message, 'error');
        }
        return false;
    }
}

async function connectViaBradySdk() {
    showToast('Brady SDK not loaded. Install with: npm install @bradycorporation/brady-web-sdk', 'warning');
    return false;
}

async function printLabel(imgElement) {
    // If BLE is connected and Brady SDK is available, print directly
    if (printerDevice && window.BradySdk && window.bradySdkInstance) {
        try {
            await window.bradySdkInstance.printBitmap(imgElement, 0.1, 0);
            return;
        } catch (err) {
            showToast('Bluetooth print failed, opening print preview instead.', 'warning');
        }
    }

    // If BLE is supported but not connected, try connecting first
    if (bleSupported && !printerDevice) {
        const connected = await connectPrinter();
        if (connected && window.BradySdk && window.bradySdkInstance) {
            try {
                await window.bradySdkInstance.printBitmap(imgElement, 0.1, 0);
                return;
            } catch (err) {
                // Fall through to dialog
            }
        }
    }

    // Fallback: open print dialog for all browsers
    printViaDialog(imgElement);
}

function printViaDialog(imgElement) {
    const printWindow = window.open('', '_blank', 'width=500,height=400');
    if (!printWindow) {
        showToast('Pop-up blocked. Please allow pop-ups for this site to print labels.', 'error');
        return;
    }
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Print Label</title>
            <style>
                * { box-sizing: border-box; margin: 0; padding: 0; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                    padding: 20px;
                    background: #f8fafc;
                }
                .label-preview {
                    border: 2px dashed #94a3b8;
                    border-radius: 8px;
                    padding: 16px;
                    background: white;
                    margin-bottom: 16px;
                }
                .label-preview img { display: block; max-width: 100%; }
                .print-btn {
                    padding: 10px 32px;
                    font-size: 16px;
                    background: #3b82f6;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                }
                .print-btn:hover { background: #2563eb; }
                .hint { margin-top: 12px; color: #64748b; font-size: 13px; }
                @media print {
                    @page { margin: 0; size: 1in 0.5in; }
                    body { padding: 0; background: white; min-height: auto; }
                    .label-preview { border: none; padding: 0; }
                    .print-btn, .hint { display: none; }
                }
            </style>
        </head>
        <body>
            <div class="label-preview">
                <img src="${imgElement.src}" />
            </div>
            <button class="print-btn" onclick="window.print()">Print Label</button>
            <div class="hint">Select your Brady M211 (or any printer) in the print dialog</div>
            <script>
                // Auto-trigger print after a short delay
                setTimeout(function() { window.print(); }, 500);
            <\/script>
        </body>
        </html>
    `);
    printWindow.document.close();
}

// Initialize printer UI on page load
document.addEventListener('DOMContentLoaded', initPrinterUI);
