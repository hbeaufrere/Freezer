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
            where box_id = %s order by row_pos, col_pos""",
        (box_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@research_bp.route('/api/research/tubes', methods=['POST'])
def create_tube():
    db = get_db()
    data = json_body()
    require(data, 'box_id', 'row_pos', 'col_pos')

    with write(db):
        tube = db.execute(
            f"""insert into research_tubes
                    (box_id, row_pos, col_pos, sample_id, description,
                     date_stored, freeze_thaw_cycles)
                values (%s, %s, %s, %s, %s, %s, %s)
                returning {_TUBE_COLUMNS}""",
            (
                as_int(data, 'box_id'),
                as_int(data, 'row_pos', minimum=1),
                as_int(data, 'col_pos', minimum=1),
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
    rows = get_db().execute(
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
    return jsonify([dict(r) for r in rows])
