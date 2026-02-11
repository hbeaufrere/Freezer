"""Research section tube CRUD endpoints."""

from flask import Blueprint, jsonify, request

research_bp = Blueprint('research', __name__)


def get_db():
    from app import get_db as _get_db
    return _get_db()


@research_bp.route('/api/research/tubes')
def list_tubes():
    db = get_db()
    box_id = request.args.get('box_id', type=int)
    if not box_id:
        return jsonify({'error': 'box_id parameter required'}), 400

    rows = db.execute("""
        SELECT id, box_id, row_pos, col_pos, sample_id, description, date_stored, created_at, updated_at
        FROM research_tubes WHERE box_id = ?
    """, (box_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@research_bp.route('/api/research/tubes', methods=['POST'])
def create_tube():
    db = get_db()
    data = request.get_json()

    required = ['box_id', 'row_pos', 'col_pos']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    try:
        db.execute(
            """INSERT INTO research_tubes (box_id, row_pos, col_pos, sample_id, description, date_stored)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data['box_id'], data['row_pos'], data['col_pos'],
             data.get('sample_id', ''), data.get('description', ''), data.get('date_stored'))
        )
        db.commit()
        tube_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        tube = db.execute("SELECT * FROM research_tubes WHERE id = ?", (tube_id,)).fetchone()
        return jsonify(dict(tube)), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@research_bp.route('/api/research/tubes/<int:tube_id>', methods=['PUT'])
def update_tube(tube_id):
    db = get_db()
    data = request.get_json()

    try:
        db.execute(
            """UPDATE research_tubes
               SET sample_id = ?, description = ?, date_stored = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (data.get('sample_id', ''), data.get('description', ''), data.get('date_stored'), tube_id)
        )
        db.commit()
        tube = db.execute("SELECT * FROM research_tubes WHERE id = ?", (tube_id,)).fetchone()
        if not tube:
            return jsonify({'error': 'Tube not found'}), 404
        return jsonify(dict(tube))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@research_bp.route('/api/research/tubes/<int:tube_id>', methods=['DELETE'])
def delete_tube(tube_id):
    db = get_db()
    db.execute("DELETE FROM research_tubes WHERE id = ?", (tube_id,))
    db.commit()
    return jsonify({'success': True})


@research_bp.route('/api/research/search')
def search_tubes():
    db = get_db()
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    rows = db.execute("""
        SELECT rt.id, rt.box_id, rt.row_pos, rt.col_pos, rt.sample_id, rt.description, rt.date_stored,
               b.label AS box_label, d.label AS drawer_label, r.label AS rack_label, sh.name AS shelf_name
        FROM research_tubes rt
        JOIN boxes b ON rt.box_id = b.id
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        WHERE rt.sample_id LIKE ? OR rt.description LIKE ?
        ORDER BY rt.sample_id
        LIMIT 50
    """, (f'%{q}%', f'%{q}%')).fetchall()
    return jsonify([dict(r) for r in rows])
