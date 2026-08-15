/* Drop-off QR codes for the satellite freezers.

   Nothing to do with tube labels. This produces a sign that gets printed once
   and taped to a freezer door at CRC or VMTH; the QR opens the public
   drop-off page for that site. */

let siteQrData = null;

async function showSiteQr(site) {
    try {
        siteQrData = await API.get(`/api/collection-sites/${site.id}/qr`);
    } catch (err) {
        showToast(err.message, 'error');
        return;
    }

    document.getElementById('site-qr-code').textContent = siteQrData.code;
    document.getElementById('site-qr-name').textContent = siteQrData.name;
    document.getElementById('site-qr-url').textContent = siteQrData.drop_url;

    renderSiteQr(document.getElementById('site-qr-stage'), siteQrData.drop_url, 7);
    bootstrap.Modal.getOrCreateInstance(document.getElementById('siteQrModal')).show();
}

/* Higher error correction than a tube label needs: this one lives on a
   freezer door and will pick up frost, fingerprints and tape. */
function renderSiteQr(stage, url, cellSize) {
    const qr = qrcode(0, 'H');
    qr.addData(url);
    qr.make();
    stage.innerHTML = qr.createSvgTag({ cellSize, margin: 4 });
    const svg = stage.querySelector('svg');
    if (svg) {
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        svg.style.width = '100%';
        svg.style.height = 'auto';
    }
}

/* Draw the QR onto a canvas at print resolution.

   The on-screen SVG is sized for a modal; a sign that goes on a freezer door
   wants real pixels, so this rasterises at roughly 1024px with the module
   grid snapped to whole pixels — a half-pixel module edge is what makes a
   printed QR fail to scan. */
function siteQrCanvas(url, targetPx = 1024, margin = 4) {
    const qr = qrcode(0, 'H');
    qr.addData(url);
    qr.make();

    const modules = qr.getModuleCount();
    const across = modules + margin * 2;
    const scale = Math.max(1, Math.floor(targetPx / across));

    const canvas = document.createElement('canvas');
    canvas.width = across * scale;
    canvas.height = across * scale;

    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#000000';
    for (let row = 0; row < modules; row++) {
        for (let col = 0; col < modules; col++) {
            if (qr.isDark(row, col)) {
                ctx.fillRect((col + margin) * scale, (row + margin) * scale, scale, scale);
            }
        }
    }
    return canvas;
}

function siteQrBlob() {
    return new Promise((resolve) => {
        siteQrCanvas(siteQrData.drop_url).toBlob(resolve, 'image/png');
    });
}

async function copySiteQrImage() {
    if (!siteQrData) return;
    const button = document.getElementById('btn-copy-site-qr');
    try {
        const blob = await siteQrBlob();
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        const icon = button.querySelector('i');
        icon.className = 'bi bi-check-lg';
        button.classList.add('is-copied');
        setTimeout(() => {
            icon.className = 'bi bi-images';
            button.classList.remove('is-copied');
        }, 1400);
    } catch (err) {
        // Firefox and older Safari have no image clipboard; the file is the
        // fallback, and it gets the user to the same place.
        showToast('This browser will not copy images — use Download instead.', 'warning');
    }
}

async function downloadSiteQr() {
    if (!siteQrData) return;
    const blob = await siteQrBlob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${siteQrData.code}-dropoff-qr.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showToast(`Saved ${siteQrData.code}-dropoff-qr.png`);
}

function printSiteQr() {
    if (!siteQrData) return;

    const qr = qrcode(0, 'H');
    qr.addData(siteQrData.drop_url);
    qr.make();

    const win = window.open('', '_blank', 'width=800,height=1000');
    if (!win) {
        showToast('Allow pop-ups for this site to print the sign.', 'error');
        return;
    }

    win.document.write(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>${escapeHtml(siteQrData.code)} drop-off</title><style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#0a1c30;
       padding:36px;text-align:center}
  .rule{height:6px;background:#ffbf00;border-radius:3px;margin-bottom:28px}
  h1{font-size:34px;letter-spacing:-0.02em;margin-bottom:4px}
  .site{font-size:19px;color:#5c7189;margin-bottom:28px}
  .qr{width:340px;margin:0 auto 26px;padding:16px;border:2px solid #0a1c30;border-radius:12px}
  .qr svg{display:block;width:100%;height:auto}
  .steps{text-align:left;max-width:430px;margin:0 auto 24px;font-size:16px;line-height:1.75}
  .steps li{margin-bottom:6px}
  .foot{font-size:12px;color:#5c7189;border-top:1px solid #c2cedd;padding-top:14px}
  @media print{body{padding:16px}}
</style></head><body>
  <div class="rule"></div>
  <h1>Raptor samples &mdash; drop-off</h1>
  <div class="site"><strong>${escapeHtml(siteQrData.code)}</strong> &middot; ${escapeHtml(siteQrData.name)}</div>
  <div class="qr">${qr.createSvgTag({ cellSize: 8, margin: 2 })}</div>
  <ol class="steps">
    <li>Put the samples in this freezer.</li>
    <li>Scan this code with your phone camera.</li>
    <li>Say how many samples you added, and tap once.</li>
  </ol>
  <div class="foot">
    CLIPR Sample Repository and Raptor Biobank &middot; the lab will collect these for the &minus;80&nbsp;&deg;C
  </div>
  <script>setTimeout(function(){window.print();},400);<\/script>
</body></html>`);
    win.document.close();
}

document.addEventListener('DOMContentLoaded', () => {
    const printBtn = document.getElementById('btn-print-site-qr');
    if (printBtn) printBtn.addEventListener('click', printSiteQr);

    const copyImg = document.getElementById('btn-copy-site-qr');
    if (copyImg) copyImg.addEventListener('click', copySiteQrImage);

    const download = document.getElementById('btn-download-site-qr');
    if (download) download.addEventListener('click', downloadSiteQr);

    attachCopyButton(document.getElementById('btn-copy-site-url'),
                     () => (siteQrData ? siteQrData.drop_url : ''));
});
