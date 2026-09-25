"""Research section tube CRUD endpoints."""

from flask import Blueprint, jsonify, request

from db import ApiError, get_db
from routes.support import (
    as_date,
    as_int,
    json_body,
    like_pattern,
    one_or_404,
    require,
    text,
    write,
)

research_bp = Blueprint('research', __name__)

_TUBE_COLUMNS = """
    id, box_id, row_pos, col_pos, sample_id, description, date_stored,
    freeze_thaw_cycles, created_at, updated_at
"""


@research_bp.route('/api/research/tubes')
def list_tubes():
    box_id = request.args.get('box_id', type=int)
    if not box_id:
        raise ApiError('box_id parameter required.')

    rows = get_db().execute(
        f"""select {_TUBE_COLUMNS} from research_tubes
            where box_id = %s
            order by row_pos nulls last, col_pos nulls last, id""",
        (box_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@research_bp.route('/api/research/tubes', methods=['POST'])
def create_tube():
    db = get_db()
    data = json_body()
    require(data, 'box_id')
    box_id = as_int(data, 'box_id')

    box = one_or_404(
        db.execute(
            'select id, box_type, grid_rows, grid_cols from boxes where id = %s', (box_id,)
        ).fetchone(),
        'Box',
    )

    if box['box_type'] == 'bulk':
        raise ApiError(
            'This box is recorded as a whole. Switch it to a grid or plain box '
            'to add samples one at a time.'
        )

    if box['box_type'] == 'plain':
        # A plain box has no wells, so any position sent with the sample is
        # dropped rather than stored: a coordinate nobody can act on is worse
        # than none at all.
        row_pos = col_pos = None

        capacity = box['grid_rows'] * box['grid_cols']
        held = db.execute(
            'select count(*) as n from research_tubes where box_id = %s', (box_id,)
        ).fetchone()['n']
        if held >= capacity:
            raise ApiError(
                f'This box already holds {held} samples, which is its capacity. '
                'Use another box.'
            )
    else:
        require(data, 'row_pos', 'col_pos')
        row_pos = as_int(data, 'row_pos', minimum=1)
        col_pos = as_int(data, 'col_pos', minimum=1)

    with write(db):
        tube = db.execute(
            f"""insert into research_tubes
                    (box_id, row_pos, col_pos, sample_id, description,
                     date_stored, freeze_thaw_cycles)
                values (%s, %s, %s, %s, %s, %s, %s)
                returning {_TUBE_COLUMNS}""",
            (
                box_id,
                row_pos,
                col_pos,
                text(data, 'sample_id'),
                text(data, 'description'),
                as_date(data, 'date_stored'),
                as_int(data, 'freeze_thaw_cycles', minimum=0, default=0),
            ),
        ).fetchone()

    return jsonify(dict(tube)), 201


@research_bp.route('/api/research/tubes/<int:tube_id>', methods=['PUT'])
def update_tube(tube_id):
    db = get_db()
    data = json_body()

    with write(db):
        tube = db.execute(
            f"""update research_tubes
                set sample_id = %s, description = %s,
                    date_stored = %s, freeze_thaw_cycles = %s
                where id = %s
                returning {_TUBE_COLUMNS}""",
            (
                text(data, 'sample_id'),
                text(data, 'description'),
                as_date(data, 'date_stored'),
                as_int(data, 'freeze_thaw_cycles', minimum=0, default=0),
                tube_id,
            ),
        ).fetchone()

    return jsonify(dict(one_or_404(tube, 'Tube')))


@research_bp.route('/api/research/tubes/<int:tube_id>/thaw', methods=['PUT'])
def record_thaw(tube_id):
    """Record one more freeze-thaw cycle for this tube."""
    db = get_db()

    with write(db):
        tube = db.execute(
            f"""update research_tubes
                set freeze_thaw_cycles = freeze_thaw_cycles + 1
                where id = %s
                returning {_TUBE_COLUMNS}""",
            (tube_id,),
        ).fetchone()

    return jsonify(dict(one_or_404(tube, 'Tube')))


@research_bp.route('/api/research/tubes/<int:tube_id>', methods=['DELETE'])
def delete_tube(tube_id):
    db = get_db()
    with write(db):
        deleted = db.execute('delete from research_tubes where id = %s', (tube_id,)).rowcount
    if not deleted:
        raise ApiError('Tube not found.', 404)
    return jsonify({'success': True})


@research_bp.route('/api/research/search')
def search_tubes():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    pattern = like_pattern(q)
    db = get_db()
    rows = db.execute(
        """select rt.id, rt.box_id, rt.row_pos, rt.col_pos, rt.sample_id,
                  rt.description, rt.date_stored, rt.freeze_thaw_cycles,
                  b.label as box_label, d.label as drawer_label,
                  r.label as rack_label, sh.name as shelf_name
           from research_tubes rt
           join boxes b on rt.box_id = b.id
           join drawers d on b.drawer_id = d.id
           join racks r on d.rack_id = r.id
           join shelves sh on r.shelf_id = sh.id
           where rt.sample_id ilike %(q)s or rt.description ilike %(q)s
           order by rt.sample_id
           limit 50""",
        {'q': pattern},
    ).fetchall()

    # Bulk boxes have no tube rows to match, so they are found by what was
    # written on them — the study or the sample type — and listed first,
    # since a whole box is a bigger find than one tube.
    boxes = db.execute(
        """select b.id as box_id, b.label as box_label, b.bulk_sample_type,
                  b.bulk_tube_count, b.bulk_study,
                  d.label as drawer_label, r.label as rack_label, sh.name as shelf_name
           from boxes b
           join drawers d on b.drawer_id = d.id
           join racks r on d.rack_id = r.id
           join shelves sh on r.shelf_id = sh.id
           where b.box_type = 'bulk'
             and (b.bulk_study ilike %(q)s or b.bulk_sample_type ilike %(q)s
                  or b.label ilike %(q)s)
           order by b.label
           limit 20""",
        {'q': pattern},
    ).fetchall()

    return jsonify(
        [{**dict(b), 'kind': 'bulk_box'} for b in boxes]
        + [{**dict(r), 'kind': 'tube'} for r in rows]
    )


# ------------------------------------------------------------
# Finding things, and the full inventory
# ------------------------------------------------------------

FILTER_PAGE_SIZE = 250


@research_bp.route('/api/research/filter-options')
def filter_options():
    """The racks worth offering — research ones, with what each holds."""
    db = get_db()
    racks = db.execute(
        """select r.id, r.label, r.designation, sh.name as shelf,
                  count(rt.id)
                  + coalesce(sum(case when b.box_type = 'bulk' then b.bulk_tube_count end)
                             filter (where rt.id is null), 0) as count
           from racks r
           join shelves sh on sh.id = r.shelf_id
           join drawers d on d.rack_id = r.id
           join boxes b on b.drawer_id = d.id
           left join research_tubes rt on rt.box_id = b.id
           where sh.section = 'research'
           group by r.id, r.label, r.designation, sh.name, sh.position, r.position
           order by sh.position, r.position"""
    ).fetchall()
    bounds = db.execute(
        'select min(date_stored) as earliest, max(date_stored) as latest from research_tubes'
    ).fetchone()
    return jsonify({
        'racks': [dict(r) for r in racks],
        'earliest': bounds['earliest'],
        'latest': bounds['latest'],
    })


@research_bp.route('/api/research/filter')
def filter_samples():
    """Samples matching the criteria, with where each one is. ``matched`` is
    the whole result, not the page: the number on screen is the number the
    download will contain."""
    from services.export_service import format_position, research_query

    filters = {
        'q': (request.args.get('q') or '').strip(),
        'rack_id': request.args.get('rack_id', type=int),
        'date_from': as_date(request.args, 'date_from'),
        'date_to': as_date(request.args, 'date_to'),
    }
    query, params = research_query(filters)
    rows = get_db().execute(query, params).fetchall()

    samples = [{
        'id': row['id'],
        'box_id': row['box_id'],
        'kind': 'tube' if row['id'] is not None else 'bulk_box',
        'sample_id': row['sample_id'],
        'description': row['description'],
        'tubes': row['tubes'],
        'date_stored': row['date_stored'],
        'freeze_thaw_cycles': row['freeze_thaw_cycles'],
        'shelf': row['shelf'], 'rack': row['rack'], 'drawer': row['drawer'], 'box': row['box'],
        'position': format_position(row['row_pos'], row['col_pos']),
    } for row in rows[:FILTER_PAGE_SIZE]]

    return jsonify({
        'matched': len(rows),
        'tubes': sum(r['tubes'] for r in rows),
        'showing': len(samples),
        'samples': samples,
    })


@research_bp.route('/api/research/inventory')
def inventory():
    """Everything in the research section, nested shelf > rack > drawer > box,
    with every sample listed under its box. Two queries, assembled here."""
    from collections import defaultdict

    from services.export_service import format_position

    db = get_db()
    boxes = db.execute(
        """select sh.id as shelf_id, sh.name as shelf, sh.position as shelf_pos,
                  r.id as rack_id, r.label as rack, r.designation, r.position as rack_pos,
                  d.id as drawer_id, d.label as drawer, d.note as drawer_note, d.position as drawer_pos,
                  b.id as box_id, b.label as box, b.position as box_pos, b.box_type,
                  b.grid_rows * b.grid_cols as capacity,
                  b.bulk_sample_type, b.bulk_tube_count, b.bulk_study, b.bulk_kind, b.bulk_fullness
           from boxes b
           join drawers d on b.drawer_id = d.id
           join racks r on d.rack_id = r.id
           join shelves sh on r.shelf_id = sh.id
           where sh.section = 'research'
           order by sh.position, r.position, d.position, b.position"""
    ).fetchall()
    tubes = db.execute(
        """select id, box_id, sample_id, description, date_stored, freeze_thaw_cycles,
                  row_pos, col_pos
           from research_tubes
           order by box_id, row_pos nulls last, col_pos nulls last, id"""
    ).fetchall()

    by_box = defaultdict(list)
    for t in tubes:
        by_box[t['box_id']].append({
            'id': t['id'], 'sample_id': t['sample_id'], 'description': t['description'],
            'date_stored': t['date_stored'], 'freeze_thaw_cycles': t['freeze_thaw_cycles'],
            'position': format_position(t['row_pos'], t['col_pos']),
        })

    shelves = []
    for row in boxes:
        shelf = shelves[-1] if shelves and shelves[-1]['id'] == row['shelf_id'] else None
        if shelf is None:
            shelf = {'id': row['shelf_id'], 'name': row['shelf'], 'racks': [], 'count': 0}
            shelves.append(shelf)
        rack = shelf['racks'][-1] if shelf['racks'] and shelf['racks'][-1]['id'] == row['rack_id'] else None
        if rack is None:
            rack = {'id': row['rack_id'], 'label': row['rack'], 'designation': row['designation'],
                    'drawers': [], 'count': 0}
            shelf['racks'].append(rack)
        drawer = rack['drawers'][-1] if rack['drawers'] and rack['drawers'][-1]['id'] == row['drawer_id'] else None
        if drawer is None:
            drawer = {'id': row['drawer_id'], 'label': row['drawer'], 'note': row['drawer_note'],
                      'boxes': [], 'count': 0}
            rack['drawers'].append(drawer)

        samples = by_box.get(row['box_id'], [])
        count = (row['bulk_tube_count'] or 0) if row['box_type'] == 'bulk' else len(samples)
        drawer['boxes'].append({
            'id': row['box_id'], 'label': row['box'], 'box_type': row['box_type'],
            'capacity': row['capacity'], 'count': count,
            'bulk_sample_type': row['bulk_sample_type'], 'bulk_study': row['bulk_study'],
            'bulk_kind': row['bulk_kind'], 'bulk_fullness': row['bulk_fullness'],
            'samples': samples,
        })
        drawer['count'] += count
        rack['count'] += count
        shelf['count'] += count

    return jsonify({'shelves': shelves, 'total': sum(s['count'] for s in shelves)})
