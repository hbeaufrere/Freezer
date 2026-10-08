/* Moving a box's contents to an empty slot, or a rack's to an empty rack.

   The destination list is built from the freezer map the page already has,
   restricted to the same section and to places with nothing in them. The
   server checks the same things again before it moves anything. */

function slotIsEmpty(box) {
    return !box.occupied && !box.bulk_sample_type && !box.bulk_study && !box.bulk_tube_count;
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

/* The small "Move…" control shown next to a box's breadcrumb. */
function moveBoxButton(box, section) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm quiet-btn move-box-btn';
    btn.innerHTML = '<i class="bi bi-arrows-move me-1"></i>Move box…';
    btn.title = 'Move everything in this box to an empty slot';
    btn.addEventListener('click', () => openMoveBoxDialog(box, section));
    return btn;
}
