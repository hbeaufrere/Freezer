/* Public drop-off page, reached by scanning the QR on a satellite freezer.

   Written for someone holding a phone in one hand and a box of tubes in the
   other: big targets, one question, and a confirmation they can see from
   arm's length. */

function initDropoff() {
    const count = document.getElementById('drop-count');

    function nudge(by) {
        const next = Math.min(500, Math.max(1, (parseInt(count.value, 10) || 1) + by));
        count.value = next;
    }

    document.getElementById('drop-minus').addEventListener('click', () => nudge(-1));
    document.getElementById('drop-plus').addEventListener('click', () => nudge(1));
    count.addEventListener('blur', () => nudge(0));

    document.getElementById('drop-submit').addEventListener('click', submitDropoff);
    document.getElementById('drop-again').addEventListener('click', () => {
        document.getElementById('drop-done').hidden = true;
        document.getElementById('drop-form').hidden = false;
        count.value = 1;
        document.getElementById('drop-note').value = '';
    });
}

async function submitDropoff() {
    const button = document.getElementById('drop-submit');
    const samples = parseInt(document.getElementById('drop-count').value, 10) || 0;

    if (samples < 1) {
        showToast('Enter at least one sample.', 'error');
        return;
    }

    button.disabled = true;
    try {
        const result = await API.post(`/api/drop/${window.DROP_TOKEN}`, {
            sample_count: samples,
            dropped_by: document.getElementById('drop-by').value.trim(),
            note: document.getElementById('drop-note').value.trim(),
        });

        document.getElementById('drop-done-title').textContent =
            `${samples} sample${samples === 1 ? '' : 's'} recorded`;
        document.getElementById('drop-done-detail').textContent =
            `${result.total_waiting} now waiting at ${result.site} for collection. `
            + 'Thank you — you can close this page.';

        document.getElementById('drop-form').hidden = true;
        document.getElementById('drop-done').hidden = false;
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        button.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', initDropoff);
