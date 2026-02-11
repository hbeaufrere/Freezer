/* Statistics page — Chart.js rendering */

const CHART_COLORS = [
    '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981',
    '#ef4444', '#06b6d4', '#f97316', '#6366f1', '#14b8a6',
    '#a855f7', '#e11d48', '#84cc16', '#0ea5e9', '#d946ef',
];

let chartInstances = {};

function destroyChart(id) {
    if (chartInstances[id]) {
        chartInstances[id].destroy();
        delete chartInstances[id];
    }
}

async function initStatsPage() {
    await Promise.all([loadRaptorStats(), loadResearchStats()]);

    // Load species for export filter
    try {
        const species = await API.get('/api/species');
        const select = document.getElementById('export-raptor-species');
        species.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.banding_code} - ${s.common_name}`;
            select.appendChild(opt);
        });
    } catch (err) {
        console.error('Failed to load species for export:', err);
    }

    // Reload when tab is shown
    document.getElementById('tab-research').addEventListener('shown.bs.tab', loadResearchStats);
    document.getElementById('tab-raptor').addEventListener('shown.bs.tab', loadRaptorStats);
}

async function loadRaptorStats() {
    try {
        const stats = await API.get('/api/stats/raptor');

        // Summary cards
        document.getElementById('raptor-total').textContent = stats.total_samples;
        const speciesCount = stats.species_breakdown ? stats.species_breakdown.length : 0;
        document.getElementById('raptor-species-count').textContent = speciesCount;
        document.getElementById('raptor-avg-ft').textContent = stats.avg_freeze_thaw_cycles;

        if (stats.species_breakdown && stats.species_breakdown.length > 0) {
            document.getElementById('raptor-most-common').textContent = stats.species_breakdown[0].code;
        } else {
            document.getElementById('raptor-most-common').textContent = 'N/A';
        }

        // Species bar chart (horizontal)
        renderSpeciesChart(stats.species_breakdown || []);

        // Monthly chart
        renderMonthlyChart(stats.monthly_counts || []);

        // Age distribution
        renderAgeChart(stats.age_distribution || []);

        // Sex distribution
        renderSexChart(stats.sex_distribution || []);

    } catch (err) {
        console.error('Failed to load raptor stats:', err);
    }
}

function renderSpeciesChart(data) {
    destroyChart('species');
    const ctx = document.getElementById('chart-species');
    if (!ctx || data.length === 0) return;

    chartInstances['species'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.code),
            datasets: [{
                label: 'Samples',
                data: data.map(d => d.count),
                backgroundColor: data.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]),
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => {
                            const idx = items[0].dataIndex;
                            return `${data[idx].species} (${data[idx].code})`;
                        }
                    }
                }
            },
            scales: {
                x: { beginAtZero: true, title: { display: true, text: 'Sample Count' } },
                y: { title: { display: false } }
            }
        }
    });
}

function renderMonthlyChart(data) {
    destroyChart('monthly');
    const ctx = document.getElementById('chart-monthly');
    if (!ctx || data.length === 0) return;

    chartInstances['monthly'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.month),
            datasets: [{
                label: 'Samples',
                data: data.map(d => d.count),
                backgroundColor: '#3b82f6',
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Count' } },
                x: { title: { display: true, text: 'Month' } }
            }
        }
    });
}

function renderAgeChart(data) {
    destroyChart('age');
    const ctx = document.getElementById('chart-age');
    if (!ctx || data.length === 0) return;

    chartInstances['age'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.age),
            datasets: [{
                label: 'Count',
                data: data.map(d => d.count),
                backgroundColor: '#10b981',
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true },
            }
        }
    });
}

function renderSexChart(data) {
    destroyChart('sex');
    const ctx = document.getElementById('chart-sex');
    if (!ctx || data.length === 0) return;

    const colorMap = { 'Male': '#3b82f6', 'Female': '#ec4899', 'Unknown': '#94a3b8' };

    chartInstances['sex'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.sex),
            datasets: [{
                label: 'Count',
                data: data.map(d => d.count),
                backgroundColor: data.map(d => colorMap[d.sex] || '#6b7280'),
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true },
            }
        }
    });
}

async function loadResearchStats() {
    try {
        const stats = await API.get('/api/stats/research');

        document.getElementById('research-total').textContent = stats.total_samples;
        document.getElementById('research-boxes-used').textContent = stats.boxes_with_samples;
        document.getElementById('research-total-boxes').textContent = stats.total_boxes;

        // Rack occupancy chart
        renderResearchRackChart(stats.occupancy_by_rack || []);

    } catch (err) {
        console.error('Failed to load research stats:', err);
    }
}

function renderResearchRackChart(data) {
    destroyChart('research-rack');
    const ctx = document.getElementById('chart-research-rack');
    if (!ctx || data.length === 0) return;

    chartInstances['research-rack'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(d => d.rack),
            datasets: [{
                label: 'Samples',
                data: data.map(d => d.count),
                backgroundColor: '#10b981',
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Tube Count' } },
            }
        }
    });
}
