/* Brady M211 Bluetooth label printer integration.
   Uses Web Bluetooth API — works in Chrome and Edge only.
   The Brady Web SDK (@bradycorporation/brady-web-sdk) is optional.
   This implementation uses a direct Web Bluetooth approach as fallback
   with the Brady SDK when available. */

let printerDevice = null;
let printerCharacteristic = null;

async function connectPrinter() {
    const statusText = document.getElementById('printer-status-text');
    try {
        // Try Brady SDK first if available
        if (window.BradySdk) {
            return await connectViaBradySdk();
        }

        // Fallback: basic Web Bluetooth connection
        if (!navigator.bluetooth) {
            showToast('Web Bluetooth is not supported in this browser. Use Chrome or Edge.', 'error');
            return false;
        }

        statusText.textContent = 'Scanning...';
        printerDevice = await navigator.bluetooth.requestDevice({
            filters: [{ namePrefix: 'M211' }],
            optionalServices: ['00001101-0000-1000-8000-00805f9b34fb']
        });

        statusText.textContent = 'Connected: ' + (printerDevice.name || 'M211');
        document.getElementById('btn-printer-connect').classList.remove('btn-outline-light');
        document.getElementById('btn-printer-connect').classList.add('btn-light');
        showToast('Printer connected: ' + (printerDevice.name || 'M211'));
        return true;
    } catch (err) {
        statusText.textContent = 'Printer';
        if (err.name !== 'NotFoundError') {
            showToast('Printer connection failed: ' + err.message, 'error');
        }
        return false;
    }
}

async function connectViaBradySdk() {
    // Brady SDK integration placeholder
    // This will be implemented when the SDK is installed
    showToast('Brady SDK not loaded. Install with: npm install @bradycorporation/brady-web-sdk', 'warning');
    return false;
}

async function printLabel(imgElement) {
    if (!printerDevice && !window.BradySdk) {
        const connected = await connectPrinter();
        if (!connected) {
            // Fallback: open print dialog with label image
            printViaDialog(imgElement);
            return;
        }
    }

    if (window.BradySdk && window.bradySdkInstance) {
        await window.bradySdkInstance.printBitmap(imgElement, 0.1, 0);
    } else {
        printViaDialog(imgElement);
    }
}

function printViaDialog(imgElement) {
    // Open browser print dialog with the label image
    const printWindow = window.open('', '_blank', 'width=400,height=300');
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Print Label</title>
            <style>
                body { margin: 0; display: flex; justify-content: center; align-items: center; }
                img { max-width: 100%; }
                @media print {
                    @page { margin: 0; size: auto; }
                    body { margin: 0; }
                }
            </style>
        </head>
        <body>
            <img src="${imgElement.src}" />
            <script>
                window.onload = function() { window.print(); window.close(); };
            <\/script>
        </body>
        </html>
    `);
    printWindow.document.close();
}

// Connect printer button handler
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('btn-printer-connect');
    if (btn) {
        btn.addEventListener('click', connectPrinter);
    }
});
