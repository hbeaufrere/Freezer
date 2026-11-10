// ==UserScript==
// @name         VMACS CBC import for RI studies
// @namespace    clipr-freezer
// @version      1.0.0
// @description  Sends a bird's CBC from VMACS to the reference-interval study in the CLIPR freezer app.
// @match        https://*.vetmed.ucdavis.edu/*
// @match        __APP_ORIGIN__/studies*
// @grant        GM.getValue
// @grant        GM.setValue
// @grant        GM.openInTab
// @grant        GM.registerMenuCommand
// @run-at       document-idle
// @noframes
// ==/UserScript==

/* What this does, and all it does:

   On VMACS it adds one button. Pressed on a case, it runs a visit search
   for the raptor-stray account, reads the saved report format that carries
   the CBC columns, keeps the rows for this one patient, and hands them to
   the freezer app. It reads; it never writes to VMACS.

   On the freezer app it passes two messages: "open VMACS for patient N"
   (from the study page, after you copy an email), and "here is the CBC"
   (to the import page). The two halves talk through Tampermonkey's own
   storage, never through the network.

   Settings (Tampermonkey menu on a VMACS page): the owner account searched,
   the report format read, and how far back to look. */

(async function () {
    'use strict';

    const APP = '__APP_ORIGIN__';
    const FRESH_MS = 3 * 60 * 1000;
    const settings = async () => ({
        owner: await GM.getValue('owner', 'VMTH Raptor Stray (V00031)'),
        format: await GM.getValue('format', 'GLDHEXPHB'),
        lookbackDays: Number(await GM.getValue('lookbackDays', 550)),
    });
    const fresh = (x) => x && x.ts && Date.now() - x.ts < FRESH_MS;
    const digits = (s) => String(s || '').replace(/\D/g, '');

    if (location.origin === APP) { appSide(); return; }
    if (!/\/vmacs2(\/|$)/i.test(location.pathname)) return;
    vmacsSide();

    /* ---------------- on the freezer app ---------------- */

    function appSide() {
        const say = (msg) => window.postMessage(msg, location.origin);
        say({ type: 'ri-userscript-ready', version: '1.0.0' });

        async function deliver() {
            const result = await GM.getValue('riResult', null);
            if (!fresh(result)) return false;
            await GM.setValue('riResult', null);
            say({ type: 'ri-import-payload', payload: result });
            return true;
        }

        window.addEventListener('message', async (event) => {
            if (event.origin !== location.origin || !event.data) return;
            if (event.data.type === 'ri-study-page-ready') say({ type: 'ri-userscript-ready', version: '1.0.0' });
            if (event.data.type === 'ri-import-page-ready') {
                // The CBC may land a moment after the page opens.
                for (let i = 0; i < 12; i += 1) {
                    if (await deliver()) return;
                    await new Promise((r) => setTimeout(r, 500));
                }
            }
            if (event.data.type === 'ri-open-vmacs') {
                const base = await GM.getValue('vmacsBase', '');
                if (!base) { say({ type: 'ri-need-vmacs' }); return; }
                await GM.setValue('riRequest', {
                    ts: Date.now(), patient: digits(event.data.patient),
                    study: event.data.study || '', wrmd: event.data.wrmd || '',
                });
                GM.openInTab(base, { active: true });
            }
        });
        if (location.pathname === '/studies/import') deliver();
    }

    /* ---------------- on VMACS ---------------- */

    async function vmacsSide() {
        const root = location.pathname.match(/^.*?\/vmacs2\//i);
        await GM.setValue('vmacsBase', location.origin + (root ? root[0] : '/Vmacs2/'));

        if (GM.registerMenuCommand) {
            const ask = (key, label, fallback) => GM.registerMenuCommand(label, async () => {
                const v = prompt(label, await GM.getValue(key, fallback));
                if (v !== null && v.trim()) await GM.setValue(key, v.trim());
            });
            ask('owner', 'RI import: owner account to search', 'VMTH Raptor Stray (V00031)');
            ask('format', 'RI import: report format with the CBC columns', 'GLDHEXPHB');
            ask('lookbackDays', 'RI import: days to look back', '550');
        }

        const box = document.createElement('div');
        box.style.cssText = 'position:fixed;right:14px;bottom:14px;z-index:2147483000;font:13px/1.35 system-ui,sans-serif;'
            + 'display:flex;flex-direction:column;align-items:flex-end;gap:6px;max-width:340px';
        const note = document.createElement('div');
        note.style.cssText = 'display:none;background:#16233a;color:#fff;padding:8px 10px;border-radius:8px;'
            + 'box-shadow:0 4px 14px rgba(0,0,0,.25);white-space:pre-wrap';
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = 'Import CBC → RI study';
        button.style.cssText = 'background:#0a2a5e;color:#fff;border:0;border-radius:999px;padding:9px 14px;'
            + 'font:600 13px system-ui,sans-serif;cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25)';
        box.append(note, button);
        document.body.appendChild(box);
        const tell = (msg, bad) => {
            note.textContent = msg; note.style.display = msg ? 'block' : 'none';
            note.style.background = bad ? '#8a1f17' : '#16233a';
        };

        let busy = false;
        async function run(target) {
            if (busy) return;
            busy = true; button.disabled = true; button.style.opacity = '.6';
            try {
                tell('Searching VMACS…');
                const found = await fetchPatientRows(target, tell);
                await GM.setValue('riResult', {
                    ts: Date.now(), study: target.study || '', wrmd: target.wrmd || '',
                    header: found.header, rows: found.rows,
                });
                tell(`Found ${found.rows.length} visit${found.rows.length === 1 ? '' : 's'}. Opening the study…`);
                if (found.latestVisit && !/#!vs\//.test(location.hash)) location.hash = '#!vs/' + found.latestVisit;
                GM.openInTab(APP + '/studies/import', { active: true });
                setTimeout(() => tell(''), 6000);
            } catch (err) {
                tell(`CBC import failed.\n${err.message}`, true);
            } finally {
                busy = false; button.disabled = false; button.style.opacity = '1';
            }
        }

        button.addEventListener('click', () => {
            const visit = (location.hash.match(/#!vs\/(\d+)/) || [])[1];
            if (visit) { run({ visit }); return; }
            const typed = prompt('No case is open. VMACS patient number to import:');
            if (typed && digits(typed)) run({ patient: digits(typed) });
        });

        // Sent here by the study page, after an email was copied.
        const request = await GM.getValue('riRequest', null);
        if (fresh(request) && request.patient) {
            await GM.setValue('riRequest', null);
            run({ patient: request.patient, study: request.study, wrmd: request.wrmd });
        }
    }

    function vmacsDate(d) {
        const m = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][d.getMonth()];
        return String(d.getDate()).padStart(2, '0') + m + d.getFullYear();
    }

    /* Run the visit search, page through the report format, and keep the
       rows for one patient. target: { visit } or { patient }. */
    async function fetchPatientRows(target, tell) {
        const cfg = await settings();
        const body = new URLSearchParams({
            ownlist: cfg.owner, date1: vmacsDate(new Date(Date.now() - cfg.lookbackDays * 864e5)),
            keywords: '', clinlist: '', proclist: '', species: '', sblist: '', date2: '',
            age1: '', age2: '', wt1: '', wt2: '', rmax: '',
        });
        const started = await fetch('/vsks', {
            method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body,
        });
        const startedText = await started.text();
        if (/<input[^>]+type=["']?password/i.test(startedText)) throw new Error('VMACS wants you to sign in first.');
        const search = (startedText.match(/Searching\s*#\s*(\d+)/i) || [])[1];
        if (!search) throw new Error('VMACS did not start a visit search. Its search form may have changed.');

        let header = null, cursor = null, pages = 0;
        const all = [];
        while (pages < 8) {
            pages += 1;
            tell(`Reading ${cfg.format}, page ${pages}…`);
            let url = `/vsks/${search}/vlist?format=${encodeURIComponent(cfg.format)}&limit=1000`;
            if (cursor) url += '&start=' + encodeURIComponent(cursor);
            const html = await (await fetch(url)).text();
            if (/processing error/i.test(html)) throw new Error(`VMACS could not render the report format ${cfg.format}.`);
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const table = doc.querySelector('table');
            if (!table) break;
            for (let i = 0; i < table.rows.length; i += 1) {
                const cells = [...table.rows[i].children]
                    .filter((c) => c.tagName === 'TD' || c.tagName === 'TH')
                    .map((c) => c.textContent.replace(/ /g, ' ').trim());
                if (i === 0) { if (!header) header = cells; continue; }
                if (cells.join('') !== '') all.push(cells);
            }
            const next = [...doc.querySelectorAll('a')]
                .map((a) => (a.getAttribute('href') || '').match(/[?&]start=([^&]*)/))
                .filter(Boolean).map((m) => decodeURIComponent(m[1]));
            const c = next.length ? next[next.length - 1] : null;
            if (!c || c === cursor) break;
            cursor = c;
        }
        if (!header) throw new Error(`The report format ${cfg.format} returned no table.`);

        const col = (...res) => header.findIndex((h) => res.some((re) => re.test(h)));
        const cVisit = col(/^visit\s*no/i, /^invoice/i);
        const cPatient = col(/^patient\s*no/i, /^ptnt\s*no/i);
        if (!header.some((h) => /^CBC/i.test(h))) {
            throw new Error(`The report format ${cfg.format} has no CBC_ columns. Its columns start: ${header.slice(0, 8).join(', ')}`);
        }
        if (cPatient < 0) throw new Error(`No PatientNo column in ${cfg.format}. Columns: ${header.slice(0, 8).join(', ')}`);

        let patient = target.patient || '';
        if (!patient && target.visit) {
            const hit = all.find((r) => cVisit >= 0 && digits(r[cVisit]) === digits(target.visit));
            if (!hit) {
                throw new Error(`Visit ${target.visit} is not among the ${all.length} visits found for ${cfg.owner} `
                    + `in the last ${cfg.lookbackDays} days. Change the owner or the look-back in the Tampermonkey menu.`);
            }
            patient = digits(hit[cPatient]);
        }
        const rows = all.filter((r) => digits(r[cPatient]) === patient);
        if (!rows.length) {
            throw new Error(`Patient ${patient} has no visit among the ${all.length} found for ${cfg.owner} `
                + `in the last ${cfg.lookbackDays} days.`);
        }
        const visits = cVisit >= 0 ? rows.map((r) => digits(r[cVisit])).filter(Boolean).sort() : [];
        return { header, rows, latestVisit: visits[visits.length - 1] || null };
    }
})();
