/* Statistics page — Chart.js rendering, theme aware. */

/* Same twelve hues as the box grid, so a species keeps its colour across
   the freezer view and the charts. */
const SERIES_COLORS = [
    '#2563a8', '#7a3f9d', '#b03060', '#99631a', '#1f7a5a', '#a8382f',
    '#0f6f7c', '#b5541c', '#4a4fa0', '#157a72', '#8e3d84', '#6b7a1f',
];

const charts = {};
let lastStats = { raptor: null, research: null };

function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function chartTheme() {
    return {
        text: cssVar('--f-muted'),
        grid: cssVar('--f-hairline'),
        accent: cssVar('--f-accent'),
        research: cssVar('--f-research'),
    };
}

function destroyChart(key) {
    if (charts[key]) {
        charts[key].destroy();
        delete charts[key];
    }
}

function baseOptions(theme, { horizontal = false } = {}) {
    const valueAxis = { beginAtZero: true, ticks: { color: theme.text, precision: 0 },
                        grid: { color: theme.grid } };
    const labelAxis = { ticks: { color: theme.text }, grid: { display: false } };

    return {
        indexAxis: horizontal ? 'y' : 'x',
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: horizontal ? { x: valueAxis, y: labelAxis } : { x: labelAxis, y: valueAxis },
    };
}

function renderBar(key, canvasId, labels, values, colors, options) {
    destroyChart(key);
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    if (!labels.length) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = cssVar('--f-muted');
        ctx.font = '13px system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No data yet', canvas.width / 2, canvas.height / 2);
        return;
    }

    charts[key] = new Chart(canvas, {
        type: 'bar',
        data: {
            labels,
            datasets: [{ data: values, backgroundColor: colors, borderRadius: 4, borderWidth: 0 }],
        },
        options,
    });
}

/* Sample types keep one colour each wherever they appear, so plasma is the
   same straw and red cells the same red on every chart. Anything else takes
   a colour from the series palette in order of appearance. */
const TYPE_COLORS = {
    'Plasma': '#d9a521', 'Packed RBCs': '#b4322a', 'Liver': '#6b4a2b',
    'Whole blood': '#8e1c1c', 'Serum': '#e3c35a', 'Unspecified': '#9aa6b8',
};

/* One stacked bar per species, one segment per sample type: how deep the
   bank is for each species, and which types are missing. */
function renderTypesBySpecies(rows, theme) {
    destroyChart('typesSpecies');
    const canvas = document.getElementById('chart-types-species');
    if (!canvas) return;
    if (!rows.length) {
        renderBar('typesSpecies', 'chart-types-species', [], [], [], {});
        return;
    }

    const speciesOrder = [];
    const totals = {};
    rows.forEach((r) => {
        if (!(r.code in totals)) { totals[r.code] = 0; speciesOrder.push({ code: r.code, species: r.species }); }
        totals[r.code] += r.count;
    });
    speciesOrder.sort((a, b) => totals[b.code] - totals[a.code] || a.species.localeCompare(b.species));

    // Blood first, in the order the form lists them; anything else after.
    const preferred = Object.keys(TYPE_COLORS);
    const types = [...new Set(rows.map((r) => r.sample_type))].sort((a, b) => {
        const ia = preferred.indexOf(a), ib = preferred.indexOf(b);
        return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
    });
    let extra = 0;
    const datasets = types.map((type) => ({
        label: type,
        data: speciesOrder.map((s) => rows.find((r) => r.code === s.code && r.sample_type === type)?.count || 0),
        backgroundColor: TYPE_COLORS[type] || SERIES_COLORS[(extra++) % SERIES_COLORS.length],
        borderWidth: 0,
        borderRadius: 2,
    }));

    const base = baseOptions(theme, { horizontal: true });
    charts.typesSpecies = new Chart(canvas, {
        type: 'bar',
        data: { labels: speciesOrder.map((s) => s.code), datasets },
        options: {
            ...base,
            scales: {
                x: { ...base.scales.x, stacked: true },
                y: { ...base.scales.y, stacked: true },
            },
            plugins: {
                legend: { display: true, position: 'top', labels: { color: theme.text, boxWidth: 12 } },
                tooltip: {
                    callbacks: {
                        title: (items) => speciesOrder[items[0].dataIndex].species,
                        footer: (items) => `${totals[speciesOrder[items[0].dataIndex].code]} tubes in all`,
                    },
                },
            },
        },
    });
}

/* ---- Raptor ----------------------------------------------- */

async function loadRaptorStats() {
    try {
        const stats = await API.get('/api/stats/raptor');
        lastStats.raptor = stats;
        drawRaptorCharts(stats);
    } catch (err) {
        console.error('Raptor stats failed to load:', err);
    }
}

function drawRaptorCharts(stats) {
    const theme = chartTheme();
    const species = stats.species_breakdown || [];

    document.getElementById('raptor-total').textContent = stats.total_samples;
    document.getElementById('raptor-tube-note').textContent = `${stats.total_tubes} tubes`;
    document.getElementById('raptor-species-count').textContent = species.length;
    document.getElementById('raptor-avg-ft').textContent = stats.avg_freeze_thaw_cycles;
    document.getElementById('raptor-most-common').textContent =
        species.length ? species[0].code : '—';

    renderBar(
        'species', 'chart-species',
        species.map((d) => d.code),
        species.map((d) => d.count),
        species.map((_, i) => SERIES_COLORS[i % SERIES_COLORS.length]),
        {
            ...baseOptions(theme, { horizontal: true }),
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => species[items[0].dataIndex].species,
                    },
                },
            },
        }
    );

    renderTypesBySpecies(stats.types_by_species || [], theme);

    const monthly = stats.monthly_counts || [];
    renderBar('monthly', 'chart-monthly',
        monthly.map((d) => d.month), monthly.map((d) => d.count),
        theme.accent, baseOptions(theme));

    const ages = stats.age_distribution || [];
    renderBar('age', 'chart-age',
        ages.map((d) => d.age), ages.map((d) => d.count),
        theme.accent, baseOptions(theme));

    const sexes = stats.sex_distribution || [];
    const sexColors = { Male: '#2563a8', Female: '#b03060', Unknown: cssVar('--f-muted') };
    renderBar('sex', 'chart-sex',
        sexes.map((d) => d.sex), sexes.map((d) => d.count),
        sexes.map((d) => sexColors[d.sex] || cssVar('--f-muted')), baseOptions(theme));
}

/* ---- Research --------------------------------------------- */

async function loadResearchStats() {
    try {
        const stats = await API.get('/api/stats/research');
        lastStats.research = stats;
        drawResearchCharts(stats);
    } catch (err) {
        console.error('Research stats failed to load:', err);
    }
}

function drawResearchCharts(stats) {
    document.getElementById('research-total').textContent = stats.total_samples;
    document.getElementById('research-boxes-used').textContent = stats.boxes_with_samples;
    document.getElementById('research-total-boxes').textContent = stats.total_boxes;
    document.getElementById('research-avg-ft').textContent = stats.avg_freeze_thaw_cycles;
}

/* ---- Page ------------------------------------------------- */

async function initStatsPage() {
    await Promise.all([loadRaptorStats(), loadResearchStats()]);

    try {
        const species = await API.get('/api/species');
        const select = document.getElementById('export-raptor-species');
        species.forEach((s) =>
            select.appendChild(new Option(`${s.banding_code} — ${s.common_name}`, s.id)));
    } catch (err) {
        console.error('Species list failed to load:', err);
    }

    // Charts sized while their tab was hidden come out wrong; redraw on show.
    document.getElementById('tab-raptor')
        .addEventListener('shown.bs.tab', () => lastStats.raptor && drawRaptorCharts(lastStats.raptor));
    document.getElementById('tab-research')
        .addEventListener('shown.bs.tab', () => lastStats.research && drawResearchCharts(lastStats.research));

    // Chart colours are baked in at build time, so rebuild them on theme change.
    document.addEventListener('themechange', () => {
        if (lastStats.raptor) drawRaptorCharts(lastStats.raptor);
        if (lastStats.research) drawResearchCharts(lastStats.research);
    });
}
