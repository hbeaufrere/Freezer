"""Freezer structure API endpoints (shelves, racks, drawers, boxes)."""

from collections import defaultdict

from flask import Blueprint, jsonify

from db import ApiError, get_db, insert_returning_id
from routes.support import as_int, json_body, one_or_404, require, text, write

freezer_bp = Blueprint('freezer', __name__)

# Occupancy per box, counting both sections. Used wherever boxes are listed.
_BOX_COLUMNS = """
    b.id, b.drawer_id, b.position, b.label, b.grid_rows, b.grid_cols, b.section,
    coalesce(rc.cnt, 0) + coalesce(rp.cnt, 0) as occupied,
    b.grid_rows * b.grid_cols as capacity
"""

_BOX_JOINS = """
    from boxes b
    left join (select box_id, count(*) as cnt from research_tubes group by box_id) rc
           on rc.box_id = b.id
    left join (select box_id, count(*) as cnt from raptor_tubes group by box_id) rp
           on rp.box_id = b.id
"""


@freezer_bp.route('/api/freezer')
def get_freezer():
    """The whole freezer as nested shelves -> racks -> drawers -> boxes.

    Four flat queries assembled in Python. Walking the hierarchy level by level
    instead would cost ~148 round-trips, which is free against a local file and
    very much not free against a hosted database.
    """
    db = get_db()

    shelves = db.execute(
        'select id, name, position, section from shelves order by position'
    ).fetchall()
    racks = db.execute(
        'select id, shelf_id, position, label, designation from racks order by position'
    ).fetchall()
    drawers = db.execute(
        'select id, rack_id, position, label from drawers order by position'
    ).fetchall()
    boxes = db.execute(f'select {_BOX_COLUMNS} {_BOX_JOINS} order by b.position').fetchall()

    boxes_by_drawer = defaultdict(list)
    for box in boxes:
        boxes_by_drawer[box['drawer_id']].append(dict(box))

    drawers_by_rack = defaultdict(list)
    for drawer in drawers:
        entry = dict(drawer)
        entry['boxes'] = boxes_by_drawer.get(drawer['id'], [])
        drawers_by_rack[drawer['rack_id']].append(entry)

    racks_by_shelf = defaultdict(list)
    for rack in racks:
        entry = dict(rack)
        entry['drawers'] = drawers_by_rack.get(rack['id'], [])
        racks_by_shelf[rack['shelf_id']].append(entry)

    result = []
    for shelf in shelves:
        entry = dict(shelf)
        entry['racks'] = racks_by_shelf.get(shelf['id'], [])
        result.append(entry)

    return jsonify(result)


@freezer_bp.route('/api/shelves')
def list_shelves():
    rows = get_db().execute(
        'select id, name, position, section from shelves order by position'
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/shelves/<int:shelf_id>/racks')
def list_racks(shelf_id):
    rows = get_db().execute(
        """select id, shelf_id, position, label, designation
           from racks where shelf_id = %s order by position""",
        (shelf_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/racks/<int:rack_id>/drawers')
def list_drawers(rack_id):
    rows = get_db().execute(
        'select id, rack_id, position, label from drawers where rack_id = %s order by position',
        (rack_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/drawers/<int:drawer_id>/boxes')
def list_boxes(drawer_id):
    rows = get_db().execute(
        f'select {_BOX_COLUMNS} {_BOX_JOINS} where b.drawer_id = %s order by b.position',
        (drawer_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/boxes/<int:box_id>')
def get_box(box_id):
    """Box details plus every tube it holds."""
    db = get_db()

    box = one_or_404(db.execute(
        """select b.id, b.position, b.label, b.grid_rows, b.grid_cols, b.section,
                  d.label as drawer_label, r.label as rack_label,
                  r.designation as rack_designation, sh.name as shelf_name
           from boxes b
           join drawers d on b.drawer_id = d.id
           join racks r on d.rack_id = r.id
           join shelves sh on r.shelf_id = sh.id
           where b.id = %s""",
        (box_id,),
    ).fetchone(), 'Box')

    box_data = dict(box)

    if box['section'] == 'raptor':
        tubes = db.execute(
            """select rt.id, rt.tube_id, rt.row_pos, rt.col_pos, rt.species_id,
                      s.banding_code, s.common_name, s.scientific_name,
                      rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
                      rt.wrmd_number, rt.vmth_number, rt.notes
               from raptor_tubes rt
               join species s on rt.species_id = s.id
               where rt.box_id = %s
               order by rt.row_pos, rt.col_pos""",
            (box_id,),
        ).fetchall()
    else:
        tubes = db.execute(
            """select id, row_pos, col_pos, sample_id, description,
                      date_stored, freeze_thaw_cycles
               from research_tubes
               where box_id = %s
               order by row_pos, col_pos""",
            (box_id,),
        ).fetchall()

    box_data['tubes'] = [dict(t) for t in tubes]
    return jsonify(box_data)


@freezer_bp.route('/api/boxes', methods=['POST'])
def create_box():
    db = get_db()
    data = json_body()
    require(data, 'drawer_id', 'position')

    section = text(data, 'section', 'research')
    if section not in ('raptor', 'research'):
        raise ApiError("Section must be either 'raptor' or 'research'.")

    with write(db):
        box_id = insert_returning_id(
            db,
            """insert into boxes (drawer_id, position, label, grid_rows, grid_cols, section)
               values (%s, %s, %s, %s, %s, %s)
               returning id""",
            (
                as_int(data, 'drawer_id'),
                as_int(data, 'position', minimum=1),
                text(data, 'label'),
                as_int(data, 'grid_rows', minimum=1, maximum=26, default=10),
                as_int(data, 'grid_cols', minimum=1, maximum=26, default=10),
                section,
            ),
        )
    return jsonify({'id': box_id}), 201


@freezer_bp.route('/api/boxes/<int:box_id>', methods=['PUT'])
def update_box(box_id):
    db = get_db()
    data = json_body()

    rows = as_int(data, 'grid_rows', minimum=1, maximum=26, default=10)
    cols = as_int(data, 'grid_cols', minimum=1, maximum=26, default=10)

    one_or_404(db.execute('select id from boxes where id = %s', (box_id,)).fetchone(), 'Box')

    # Shrinking a grid must not strand tubes outside the new bounds, where they
    # would still count towards occupancy but never appear in the grid again.
    stranded = db.execute(
        """select count(*) as n from (
               select row_pos, col_pos from research_tubes where box_id = %(box)s
               union all
               select row_pos, col_pos from raptor_tubes where box_id = %(box)s
           ) t
           where t.row_pos > %(rows)s or t.col_pos > %(cols)s""",
        {'box': box_id, 'rows': rows, 'cols': cols},
    ).fetchone()['n']

    if stranded:
        raise ApiError(
            f'{stranded} tube(s) sit outside a {rows}x{cols} grid. '
            'Move them first, then resize the box.'
        )

    with write(db):
        db.execute(
            'update boxes set label = %s, grid_rows = %s, grid_cols = %s where id = %s',
            (text(data, 'label'), rows, cols, box_id),
        )
    return jsonify({'success': True})


@freezer_bp.route('/api/boxes/<int:box_id>', methods=['DELETE'])
def delete_box(box_id):
    db = get_db()

    occupied = db.execute(
        """select (select count(*) from research_tubes where box_id = %(box)s)
                + (select count(*) from raptor_tubes where box_id = %(box)s) as n""",
        {'box': box_id},
    ).fetchone()['n']

    if occupied:
        raise ApiError(f'This box still holds {occupied} tube(s). Empty it first.')

    with write(db):
        deleted = db.execute('delete from boxes where id = %s', (box_id,)).rowcount

    if not deleted:
        raise ApiError('Box not found.', 404)
    return jsonify({'success': True})
