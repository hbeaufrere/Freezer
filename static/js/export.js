/* Export button handlers */

function initExportButtons() {
    document.getElementById('btn-export-raptor-xlsx').addEventListener('click', () => exportRaptor('xlsx'));
    document.getElementById('btn-export-raptor-csv').addEventListener('click', () => exportRaptor('csv'));
    document.getElementById('btn-export-research-xlsx').addEventListener('click', () => exportResearch('xlsx'));
    document.getElementById('btn-export-research-csv').addEventListener('click', () => exportResearch('csv'));
}

function exportRaptor(format) {
    const speciesId = document.getElementById('export-raptor-species').value;
    const dateFrom = document.getElementById('export-raptor-from').value;
    const dateTo = document.getElementById('export-raptor-to').value;

    const params = new URLSearchParams();
    if (speciesId) params.set('species_id', speciesId);
    if (dateFrom) params.set('date_from', dateFrom);
    if (dateTo) params.set('date_to', dateTo);

    const qs = params.toString() ? '?' + params.toString() : '';
    window.location.href = `/api/export/raptor/${format}${qs}`;
}

function exportResearch(format) {
    window.location.href = `/api/export/research/${format}`;
}
