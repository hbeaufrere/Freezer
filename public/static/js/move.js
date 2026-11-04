/* Moving a box's contents to an empty slot, or a rack's to an empty rack.

   The destination list is built from the freezer map the page already has,
   restricted to the same section and to places with nothing in them. The
   server checks the same things again before it moves anything. */

function slotIsEmpty(box) {
    return !box.occupied && !box.bulk_sample_type && !box.bulk_study && !box.bulk_tube_count;
}

function drawerIsEmpty(drawer) {
    return drawer.boxes.every(slotIsEmpty);
}

function drawerHasAnything(drawer) {
    return Boolean(drawer.note) || !drawerIsEmpty(drawer);
}

function emptyDrawerOptions(shelves, section, exceptDrawerId) {
    return shelves.filter((s) => s.section === section).flatMap((shelf) =>
        shelf.racks.map((rack) => ({
            group: `${shelf.name} › ${rack.label}${rack.designation ? ' — ' + rack.designation : ''}`,
            slots: rack.drawers.filter((d) => d.id !== exceptDrawerId && drawerIsEmpty(d))
                .map((d) => ({ id: d.id, label: `${d.label || 'D' + d.position}${d.position === 1 ? ' · top' : ''}` })),
        }))).filter((g) => g.slots.length);
}

function rackIsEmpty(rack) {
    return rack.drawers.every((d) => d.boxes.every(slotIsEmpty));
}

function rackHasAnything(rack) {
    return Boolean(rack.designation) || rack.drawers.some((d) => d.note || d.boxes.some((b) => !slotIsEmpty(b)));
}

/* Walk the map and offer every empty slot in this section, grouped by rack
   so a long list still reads as the freezer does. */
function emptySlotOptions(shelves, section, exceptBoxId) {
    return shelves.filter((s) => s.section === section).flatMap((shelf) =>
        shelf.racks.map((rack) => {
            const slots = rack.drawers.flatMap((d) => d.boxes
                .filter((b) => b.id !== exceptBoxId && slotIsEmpty(b))
                .map((b) => ({ id: b.id, label: `${b.label} · ${depthLabel(b.position, d.boxes.length)}` })));
            return { group: `${shelf.name} › ${rack.label}${rack.designation ? ' — ' + rack.designation : ''}`, slots };
        })).filter((g) => g.slots.length);
}

function emptyRackOptions(shelves, section, exceptRackId) {
    return shelves.filter((s) => s.section === section).map((shelf) => ({
        group: shelf.name,
        slots: shelf.racks.filter((r) => r.id !== exceptRackId && rackIsEmpty(r))
            .map((r) => ({ id: r.id, label: r.label + (r.designation ? ` — ${r.designation} (name will be replaced)` : '') })),
    })).filter((g) => g.slots.length);
}

function fillMoveSelect(groups) {
    const select = document.getElementById('move-target');
    select.innerHTML = groups.map((g) => `
        <optgroup label="${escapeHtml(g.group)}">
            ${g.slots.map((s) => `<option value="${s.id}">${escapeHtml(s.label)}</option>`).join('')}
        </optgroup>`).join('');
    return groups.reduce((n, g) => n + g.slots.length, 0);
}

let moveAction = null;

function showMoveModal(title, what, hint, groups, action) {
    document.getElementById('move-title').textContent = title;
    document.getElementById('move-what').textContent = what;
    document.getElementById('move-hint').textContent = hint;
    const n = fillMoveSelect(groups);
    const save = document.getElementById('btn-move-save');
    save.disabled = n === 0;
    if (n === 0) {
        document.getElementById('move-target').innerHTML = '<option>No empty place to move to</option>';
    }
    moveAction = action;
    bootstrap.Modal.getOrCreateInstance(document.getElementById('moveModal')).show();
}

/* box: the box as GET /api/boxes/<id> returns it. */
async function openMoveBoxDialog(box, section) {
    let shelves;
    try { shelves = await API.get('/api/freezer'); } catch (err) { showToast(err.message, 'error'); return; }

    const count = box.box_type === 'bulk'
        ? `a whole-box entry of ${box.bulk_tube_count || 0}`
        : `${(box.tubes || []).length} sample${(box.tubes || []).length === 1 ? '' : 's'}`;
    showMoveModal(
        'Move box',
        `${box.label} holds ${count}. Everything in it moves together, positions included, and ${box.label} is left empty.`,
        'Only empty slots in this section are listed. The tube IDs do not change; only where they are.',
        emptySlotOptions(shelves, section, box.id),
        async (targetId) => {
            const result = await API.post(`/api/boxes/${box.id}/move`, { target_box_id: targetId });
            showToast(`${result.from} moved to ${result.to}`);
            document.dispatchEvent(new CustomEvent('boxmoved', {
                detail: { section, fromBoxId: box.id, toBoxId: result.target_box_id },
            }));
        },
    );
}

/* drawer: as the freezer map has it. */
async function openMoveDrawerDialog(drawer, section) {
    let shelves;
    try { shelves = await API.get('/api/freezer'); } catch (err) { showToast(err.message, 'error'); return; }

    const boxes = drawer.boxes.filter((b) => !slotIsEmpty(b)).length;
    showMoveModal(
        'Move drawer',
        `${drawer.label}${drawer.note ? ` (${drawer.note})` : ''} holds ${boxes} box${boxes === 1 ? '' : 'es'} with samples. `
        + 'Each box moves to the same slot in the new drawer; the drawer label goes with it.',
        'Only drawers with nothing in them are listed.',
        emptyDrawerOptions(shelves, section, drawer.id),
        async (targetId) => {
            const result = await API.post(`/api/drawers/${drawer.id}/move`, { target_drawer_id: targetId });
            showToast(`${result.from} moved to ${result.to}: ${result.boxes_moved} box(es), ${result.tubes_moved} tube(s)`);
            document.dispatchEvent(new CustomEvent('rackmoved', {
                detail: { section, toDrawerId: result.target_drawer_id, boxMap: result.box_map },
            }));
        },
    );
}

/* rack: as the freezer map has it. */
async function openMoveRackDialog(rack, section) {
    let shelves;
    try { shelves = await API.get('/api/freezer'); } catch (err) { showToast(err.message, 'error'); return; }

    const tubes = rack.drawers.reduce((n, d) => n + d.boxes.reduce((m, b) => m + (b.occupied || 0), 0), 0);
    const boxes = rack.drawers.reduce((n, d) => n + d.boxes.filter((b) => !slotIsEmpty(b)).length, 0);
    showMoveModal(
        'Move rack',
        `${rack.label}${rack.designation ? ` (${rack.designation})` : ''} holds ${boxes} box${boxes === 1 ? '' : 'es'} with samples. `
        + 'Every box moves to the same drawer and slot in the new rack; the rack name and drawer labels go with it.',
        'Only racks with nothing in them are listed.',
        emptyRackOptions(shelves, section, rack.id),
        async (targetId) => {
            const result = await API.post(`/api/racks/${rack.id}/move`, { target_rack_id: targetId });
            showToast(`${result.from} moved to ${result.to}: ${result.boxes_moved} box(es), ${result.tubes_moved} tube(s)`);
            document.dispatchEvent(new CustomEvent('rackmoved', {
                detail: { section, fromRackId: rack.id, toRackId: result.target_rack_id, boxMap: result.box_map },
            }));
        },
    );
}

document.addEventListener('DOMContentLoaded', () => {
    const save = document.getElementById('btn-move-save');
    if (!save) return;
    save.addEventListener('click', async () => {
        const targetId = parseInt(document.getElementById('move-target').value, 10);
        if (!targetId || !moveAction) return;
        save.disabled = true;
        try {
            await moveAction(targetId);
            bootstrap.Modal.getInstance(document.getElementById('moveModal')).hide();
        } catch (err) {
            showToast(err.message, 'error');
        } finally {
            save.disabled = false;
        }
    });
});

/* The tools shown next to a box's breadcrumb: move it, thaw it whole, or
   clear it. Clear is the odd one out — deliberately quiet, deliberately
   demanding, and the only write in the app that leaves no activity entry. */
function boxToolButtons(box, section) {
    const wrap = document.createElement('span');
    wrap.className = 'box-tools';

    const move = document.createElement('button');
    move.type = 'button';
    move.className = 'btn btn-sm quiet-btn move-box-btn';
    move.innerHTML = '<i class="bi bi-arrows-move me-1"></i>Move box…';
    move.title = 'Move everything in this box to an empty slot';
    move.addEventListener('click', () => openMoveBoxDialog(box, section));
    wrap.appendChild(move);

    const tubes = (box.tubes || []).length;
    const bulkHasEntry = box.box_type === 'bulk' && (box.bulk_sample_type || box.bulk_tube_count || box.bulk_study);
    if (tubes || bulkHasEntry) {
        const retrieve = document.createElement('button');
        retrieve.type = 'button';
        retrieve.className = 'btn btn-sm quiet-btn';
        retrieve.innerHTML = '<i class="bi bi-box-arrow-up me-1"></i>Log retrieval (box)';
        retrieve.title = box.box_type === 'bulk'
            ? 'Log a retrieval of this whole-box entry'
            : `Log one retrieval for all ${tubes} tube${tubes === 1 ? '' : 's'} in this box`;
        retrieve.addEventListener('click', () => {
            if (box.box_type === 'bulk') openRetrievalModalWholeBox(section, box);
            else openRetrievalModalBulk(section, box.tubes.map((t) => t.id),
                box.tubes.map((t) => t.tube_id || t.sample_id || 'Untitled'));
        });
        wrap.appendChild(retrieve);
    }
    if (tubes || bulkHasEntry) {
        const thaw = document.createElement('button');
        thaw.type = 'button';
        thaw.className = 'btn btn-sm quiet-btn';
        thaw.innerHTML = '<i class="bi bi-thermometer-half me-1"></i>Freeze-thaw box';
        thaw.title = bulkHasEntry
            ? `Count one freeze-thaw cycle on this whole-box entry (now ${box.bulk_freeze_thaw || 0})`
            : 'Count one freeze-thaw cycle on every tube in this box';
        thaw.addEventListener('click', async () => {
            const ask = bulkHasEntry
                ? `Count one freeze-thaw cycle on the whole-box entry in ${box.label}? It is at ${box.bulk_freeze_thaw || 0} now.`
                : `Count one freeze-thaw cycle on all ${tubes} tube${tubes === 1 ? '' : 's'} in ${box.label}?`;
            if (!confirm(`${ask}\n\nFor when the whole box came out of the freezer and went back.`)) return;
            try {
                const r = await API.post(`/api/boxes/${box.id}/thaw`, {});
                showToast(r.freeze_thaw_cycles !== undefined
                    ? `Freeze-thaw cycle recorded — ${r.box} now at ${r.freeze_thaw_cycles}`
                    : `Freeze-thaw cycle recorded on ${r.thawed} tube${r.thawed === 1 ? '' : 's'} in ${r.box}`);
                document.dispatchEvent(new CustomEvent('boxchanged', { detail: { section, boxId: box.id } }));
            } catch (err) { showToast(err.message, 'error'); }
        });
        wrap.appendChild(thaw);
    }

    const hasAnything = tubes || box.box_type === 'bulk';
    if (hasAnything) {
        const clear = document.createElement('button');
        clear.type = 'button';
        clear.className = 'btn reconcile-btn';
        clear.innerHTML = '<i class="bi bi-eraser me-1"></i>Clear box';
        clear.title = 'Erase everything in this box — reconciling only';
        clear.addEventListener('click', () => {
            const what = box.box_type === 'bulk' ? 'its whole-box entry' : `${tubes} sample${tubes === 1 ? '' : 's'}`;
            openDeleteDialog({
                title: 'Clear box',
                what: `Erase ${what} from ${box.label} and leave it an empty grid. Each erased record is logged as a deletion.`,
                confirmLabel: box.label,
                onConfirm: async (why) => {
                    const r = await API.post(`/api/boxes/${box.id}/clear`, why);
                    showToast(r.was_whole_box ? `${r.box} cleared` : `${r.box} cleared — ${r.removed} record(s) deleted`);
                    document.dispatchEvent(new CustomEvent('boxchanged', { detail: { section, boxId: box.id } }));
                },
            });
        });
        wrap.appendChild(clear);
    }
    return wrap;
}
