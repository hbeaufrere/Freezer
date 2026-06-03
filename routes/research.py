"""Research section tube CRUD endpoints."""

from flask import Blueprint, jsonify, request

from db import get_db
from auth import require_role

research_bp = Blueprint('research', __name__)


def _fetch_research_tube(db, tube_id):
    return db.execute(
        """SELECT id, box_id, row_pos, col_pos, sample_id, description, date_stored,
                  freeze_thaw_cycles, created_at, updated_at
           FROM research_tubes WHERE id = %s""",
        (tube_id,)
    ).fetchone()


@research_bp.route('/api/research/tubes')
@require_role('clipr')
def list_tubes():
    box_id = request.args.get('box_id', type=int)
    if not box_id:
        return jsonify({'error': 'box_id parameter required'}), 400

    rows = get_db().execute("""
        SELECT id, box_id, row_pos, col_pos, sample_id, description, date_stored,
               freeze_thaw_cycles, created_at, updated_at
        FROM research_tubes WHERE box_id = %s
    """, (box_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@research_bp.route('/api/research/tubes', methods=['POST'])
@require_role('clipr')
def create_tube():
    db = get_db()
    data = request.get_json()

    required = ['box_id', 'row_pos', 'col_pos']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    try:
        tube_id = db.execute(
            """INSERT INTO research_tubes (box_id, row_pos, col_pos, sample_id, description, date_stored, freeze_thaw_cycles)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (data['box_id'], data['row_pos'], data['col_pos'],
             data.get('sample_id', ''), data.get('description', ''),
             data.get('date_stored') or None, data.get('freeze_thaw_cycles', 0))
        ).fetchone()['id']
        tube = _fetch_research_tube(db, tube_id)
        db.commit()
        return jsonify(dict(tube)), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@research_bp.route('/api/research/tubes/<int:tube_id>', methods=['PUT'])
@require_role('clipr')
def update_tube(tube_id):
    db = get_db()
    data = request.get_json()

    try:
        db.execute(
            """UPDATE research_tubes
               SET sample_id = %s, description = %s, date_stored = %s,
                   freeze_thaw_cycles = %s, updated_at = now()
               WHERE id = %s""",
            (data.get('sample_id', ''), data.get('description', ''),
             data.get('date_stored') or None, data.get('freeze_thaw_cycles', 0), tube_id)
        )
        tube = _fetch_research_tube(db, tube_id)
        if not tube:
            db.rollback()
            return jsonify({'error': 'Tube not found'}), 404
        db.commit()
        return jsonify(dict(tube))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@research_bp.route('/api/research/tubes/<int:tube_id>/thaw', methods=['PUT'])
@require_role('clipr')
def record_thaw(tube_id):
    """Increment freeze-thaw cycle count by 1."""
    db = get_db()
    db.execute(
        "UPDATE research_tubes SET freeze_thaw_cycles = freeze_thaw_cycles + 1, updated_at = now() WHERE id = %s",
        (tube_id,)
    )
    tube = _fetch_research_tube(db, tube_id)
    if not tube:
        db.rollback()
        return jsonify({'error': 'Tube not found'}), 404
    db.commit()
    return jsonify(dict(tube))


@research_bp.route('/api/research/tubes/<int:tube_id>', methods=['DELETE'])
@require_role('clipr')
def delete_tube(tube_id):
    db = get_db()
    db.execute("DELETE FROM research_tubes WHERE id = %s", (tube_id,))
    db.commit()
    return jsonify({'success': True})


@research_bp.route('/api/research/search')
@require_role('clipr')
def search_tubes():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    pattern = f'%{q}%'
    rows = get_db().execute("""
        SELECT rt.id, rt.box_id, rt.row_pos, rt.col_pos, rt.sample_id, rt.description,
               rt.date_stored, rt.freeze_thaw_cycles,
               b.label AS box_label, d.label AS drawer_label, r.label AS rack_label, sh.name AS shelf_name
        FROM research_tubes rt
        JOIN boxes b ON rt.box_id = b.id
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        WHERE rt.sample_id ILIKE %s OR rt.description ILIKE %s
        ORDER BY rt.sample_id
        LIMIT 50
    """, (pattern, pattern)).fetchall()
    return jsonify([dict(r) for r in rows])
