/* Shared utilities: API client, toasts, theming, grid position labels. */

const API = {
    async _send(url, method, data) {
        const options = { method, headers: {} };
        if (data !== undefined) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(data);
        }

        const res = await fetch(url, options);

        // The session expired or was never established — get a fresh login.
        if (res.status === 401) {
            window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
            throw new Error('Signed out');
        }

        const body = await res.json().catch(() => null);
        if (!res.ok) {
            throw new Error((body && body.error) || res.statusText || 'Request failed');
        }
        return body;
    },

    get(url) { return API._send(url, 'GET'); },
    post(url, data) { return API._send(url, 'POST', data ?? {}); },
    put(url, data) { return API._send(url, 'PUT', data ?? {}); },
    del(url) { return API._send(url, 'DELETE'); },
};

/* Escape text before it goes into innerHTML. Sample IDs, descriptions and
   notes are free text, so they must never be treated as markup. */
function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const tone = { error: 'text-bg-danger', warning: 'text-bg-warning', success: 'text-bg-success' };
    const icon = { error: 'exclamation-octagon', warning: 'exclamation-triangle', success: 'check-circle' };

    const el = document.createElement('div');
    el.className = `toast align-items-center border-0 ${tone[type] || tone.success}`;
    el.setAttribute('role', 'alert');
    el.innerHTML = `
        <div class="d-flex">
            <div class="toast-body d-flex align-items-center gap-2">
                <i class="bi bi-${icon[type] || icon.success}"></i>
                <span>${escapeHtml(message)}</span>
            </div>
            <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast"
                    aria-label="Close"></button>
        </div>`;

    container.appendChild(el);
    const toast = new bootstrap.Toast(el, { delay: type === 'error' ? 6000 : 3000 });
    toast.show();
    el.addEventListener('hidden.bs.toast', () => el.remove());
}

/* Row letters skip I, which reads as 1 on a frosted label. */
const ROW_LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K'];

function positionLabel(row, col) {
    // Samples in a plain box have no coordinates. Without this the arithmetic
    // below quietly produces "@null" and prints it next to a sample ID.
    if (row === null || row === undefined || col === null || col === undefined) {
        return 'no fixed position';
    }
    const letter = ROW_LABELS[row - 1] || String.fromCharCode(64 + row);
    return `${letter}${col}`;
}

function debounce(fn, ms = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}

function today() {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    return new Date(now - offset).toISOString().slice(0, 10);
}

/* ---- Theme ------------------------------------------------ */

const THEME_KEY = 'freezer-theme';

function currentTheme() {
    return document.documentElement.getAttribute('data-bs-theme') || 'light';
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* private mode */ }

    const icon = document.getElementById('theme-icon');
    if (icon) icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';

    // Charts read CSS colours at build time, so they need rebuilding.
    document.dispatchEvent(new CustomEvent('themechange', { detail: { theme } }));
}

function initTheme() {
    applyTheme(currentTheme());
    const btn = document.getElementById('btn-theme');
    if (btn) {
        btn.addEventListener('click', () =>
            applyTheme(currentTheme() === 'dark' ? 'light' : 'dark')
        );
    }
}

/* ---- Search dropdown keyboard support --------------------- */

/* Wires arrow-key and Enter navigation onto a results dropdown, so a
   scanned tube ID can be chased down without reaching for the mouse. */
function attachSearchKeys(input, dropdown) {
    input.addEventListener('keydown', (event) => {
        const items = [...dropdown.querySelectorAll('.search-result-item[data-selectable]')];
        if (!items.length) return;

        const active = dropdown.querySelector('.search-result-item.active');
        let index = items.indexOf(active);

        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            index = event.key === 'ArrowDown'
                ? Math.min(index + 1, items.length - 1)
                : Math.max(index - 1, 0);
            items.forEach((el) => el.classList.remove('active'));
            items[index].classList.add('active');
            items[index].scrollIntoView({ block: 'nearest' });
        } else if (event.key === 'Enter' && active) {
            event.preventDefault();
            active.click();
        } else if (event.key === 'Escape') {
            dropdown.classList.remove('show');
            input.setAttribute('aria-expanded', 'false');
        }
    });
}

/* ---- Clipboard -------------------------------------------- */

async function copyText(text) {
    // The async clipboard API needs a secure context, which Vercel and
    // localhost both provide — but fall back rather than fail silently.
    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            return true;
        }
    } catch (e) { /* fall through to the textarea route */ }

    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    let copied = false;
    try { copied = document.execCommand('copy'); } catch (e) { copied = false; }
    area.remove();
    return copied;
}

/* Turns a button into a copy affordance that confirms itself with a tick,
   rather than firing a toast for something this small. */
function attachCopyButton(button, getText) {
    if (!button) return;
    button.addEventListener('click', async () => {
        const text = (getText() || '').trim();
        if (!text) return;

        const icon = button.querySelector('i');
        if (await copyText(text)) {
            icon.className = 'bi bi-check-lg';
            button.classList.add('is-copied');
            button.title = 'Copied';
            setTimeout(() => {
                icon.className = 'bi bi-clipboard';
                button.classList.remove('is-copied');
                button.title = 'Copy';
            }, 1400);
        } else {
            showToast('Could not reach the clipboard — select the ID and copy it.', 'error');
        }
    });
}

/* ---- Schema drift ----------------------------------------- */

/* Deploying a column the database has not got would otherwise surface as an
   unexplained failure on whichever page happens to need it. Ask once per page
   load, and offer to fix it in place. */
async function checkSchema() {
    const banner = document.getElementById('schema-banner');
    if (!banner) return;

    let health;
    try {
        health = await (await fetch('/api/health')).json();
    } catch (e) {
        return;  // Offline or asleep; the pages will report their own errors.
    }
    if (!health || health.schema !== 'out of date') return;

    const count = (health.pending_migrations || []).length;
    document.getElementById('schema-banner-detail').textContent =
        `${count} update${count === 1 ? '' : 's'} to apply before the app will work properly.`;
    banner.hidden = false;

    document.getElementById('btn-apply-migrations').addEventListener('click', applyMigrations);
}

async function applyMigrations() {
    const button = document.getElementById('btn-apply-migrations');
    button.disabled = true;
    button.textContent = 'Updating…';
    try {
        const result = await API.post('/api/admin/migrate');
        showToast(`Database updated (${result.count} applied). Reloading…`);
        setTimeout(() => window.location.reload(), 900);
    } catch (err) {
        showToast(err.message, 'error');
        button.disabled = false;
        button.textContent = 'Update now';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    checkSchema();
});
