"""Moving things: a box's contents to an empty slot, or a whole rack's to an
empty rack.

The freezer's structure is fixed — every drawer already has its four box
slots, every shelf its racks — so "moving a box" cannot mean moving a row in
the boxes table. It means carrying what the slot holds (tubes, or a whole-box
entry, and the slot's type) to another slot and leaving the first one empty.
A rack move does the same for every slot in the rack, position for position,
and carries the rack's name and drawer notes with it.

Both are one transaction: a half-moved rack would be worse than an unmoved
one. The destination must be empty, since a move is a relocation, never a
merge — merging two boxes of positioned tubes would need a decision per tube.
"""

from flask import Blueprint, jsonify

from db import ApiError, get_db
from routes.support import as_int, json_body, one_or_404, require, write

move_bp = Blueprint('move', __name__)

_BOX_STATE = """
    select b.id, b.label, b.section, b.drawer_id, b.position, b.grid_rows, b.grid_cols,
           b.box_type, b.bulk_sample_type, b.bulk_tube_count, b.bulk_study,
           b.bulk_kind, b.bulk_fullness, b.bulk_date,
           (select count(*) from research_tubes rt where rt.box_id = b.id)
             + (select count(*) from raptor_tubes rp where rp.box_id = b.id) as tubes,
           d.rack_id, d.position as drawer_position, r.label as rack_label
    from boxes b
    join drawers d on b.drawer_id = d.id
    join racks r on d.rack_id = r.id
"""


def _box_state(db, box_id):
    return one_or_404(db.execute(f'{_BOX_STATE} where b.id = %s', (box_id,)).fetchone(), 'Box')


def _is_empty(box):
    """No tubes, and no whole-box entry with anything written on it."""
    return box['tubes'] == 0 and not (
        box['bulk_sample_type'] or box['bulk_study'] or box['bulk_tube_count'])


def _carry_box(db, src, dst):
    """Move one slot's contents onto another, already-checked-empty slot."""
    table = 'raptor_tubes' if src['section'] == 'raptor' else 'research_tubes'
    moved = db.execute(f'update {table} set box_id = %s where box_id = %s',
                       (dst['id'], src['id'])).rowcount
    db.execute(
        """update boxes set box_type = %s, bulk_sample_type = %s, bulk_tube_count = %s,
               bulk_study = %s, bulk_kind = %s, bulk_fullness = %s, bulk_date = %s
           where id = %s""",
        (src['box_type'], src['bulk_sample_type'], src['bulk_tube_count'], src['bulk_study'],
         src['bulk_kind'], src['bulk_fullness'], src['bulk_date'], dst['id']),
    )
    db.execute(
        """update boxes set box_type = 'grid', bulk_sample_type = null, bulk_tube_count = null,
               bulk_study = null, bulk_kind = 'tubes', bulk_fullness = null, bulk_date = null
           where id = %s""",
        (src['id'],),
    )
    return moved


def _same_shape(a, b):
    return a['grid_rows'] == b['grid_rows'] and a['grid_cols'] == b['grid_cols']


@move_bp.route('/api/boxes/<int:box_id>/move', methods=['POST'])
def move_box(box_id):
    db = get_db()
    data = json_body()
    require(data, 'target_box_id')
    target_id = as_int(data, 'target_box_id')

    src = _box_state(db, box_id)
    if target_id == box_id:
        raise ApiError('That is the box it is already in.')
    dst = _box_state(db, target_id)

    if src['section'] != dst['section']:
        raise ApiError('A box can only move within its own section.')
    if not _same_shape(src, dst):
        raise ApiError('The destination box is a different size.')
    if not _is_empty(dst):
        raise ApiError(f'{dst["label"]} is not empty. A move needs an empty slot; '
                       'it never merges two boxes.', 409)
    if _is_empty(src) and src['box_type'] == 'grid':
        raise ApiError(f'{src["label"]} is empty; there is nothing to move.')

    with write(db):
        moved = _carry_box(db, src, dst)

    return jsonify({'from': src['label'], 'to': dst['label'], 'target_box_id': dst['id'],
                    'tubes_moved': moved, 'box_type': src['box_type']})


def _rack_boxes(db, rack_id):
    rows = db.execute(f'{_BOX_STATE} where d.rack_id = %s order by d.position, b.position',
                      (rack_id,)).fetchall()
    return {(r['drawer_position'], r['position']): r for r in rows}


@move_bp.route('/api/racks/<int:rack_id>/move', methods=['POST'])
def move_rack(rack_id):
    db = get_db()
    data = json_body()
    require(data, 'target_rack_id')
    target_id = as_int(data, 'target_rack_id')
    if target_id == rack_id:
        raise ApiError('That is the rack it already is.')

    def rack(rid):
        return one_or_404(db.execute(
            """select r.id, r.label, r.designation, sh.section
               from racks r join shelves sh on r.shelf_id = sh.id where r.id = %s""",
            (rid,)).fetchone(), 'Rack')

    src, dst = rack(rack_id), rack(target_id)
    if src['section'] != dst['section']:
        raise ApiError('A rack can only move within its own section.')

    src_boxes, dst_boxes = _rack_boxes(db, rack_id), _rack_boxes(db, target_id)
    if set(src_boxes) != set(dst_boxes):
        raise ApiError('The two racks are not laid out the same way.')
    for key, box in src_boxes.items():
        if not _same_shape(box, dst_boxes[key]):
            raise ApiError('The two racks hold boxes of different sizes.')
    occupied = [b['label'] for b in dst_boxes.values() if not _is_empty(b)]
    if occupied:
        raise ApiError(f'{dst["label"]} is not empty ({", ".join(occupied[:4])}'
                       f'{"…" if len(occupied) > 4 else ""}). A move needs an empty rack.', 409)

    notes = db.execute('select position, note from drawers where rack_id = %s', (rack_id,)).fetchall()

    tubes_moved = boxes_moved = 0
    box_map = {}
    with write(db):
        for key, box in src_boxes.items():
            target = dst_boxes[key]
            box_map[box['id']] = target['id']
            if _is_empty(box) and box['box_type'] == 'grid':
                continue
            tubes_moved += _carry_box(db, box, target)
            boxes_moved += 1
        # The rack's name travels with its contents, and so do the drawer
        # labels: "Bearded dragon research" describes what is in the drawer,
        # not the drawer.
        db.execute('update racks set designation = %s where id = %s', (src['designation'], target_id))
        db.execute('update racks set designation = null where id = %s', (rack_id,))
        for n in notes:
            db.execute('update drawers set note = %s where rack_id = %s and position = %s',
                       (n['note'], target_id, n['position']))
        db.execute('update drawers set note = null where rack_id = %s', (rack_id,))

    return jsonify({'from': src['label'], 'to': dst['label'], 'target_rack_id': target_id,
                    'tubes_moved': tubes_moved, 'boxes_moved': boxes_moved,
                    'box_map': box_map})
