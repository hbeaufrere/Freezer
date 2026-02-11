"""Raptor biobank tube CRUD endpoints with auto-ID generation."""

from flask import Blueprint, jsonify, request
from services.id_generator import generate_raptor_tube_id

raptor_bp = Blueprint('raptor', __name__)


def get_db():
    from app import get_db as _get_db
    return _get_db()


@raptor_bp.route('/api/raptor/tubes')
def list_tubes():
    db = get_db()
    box_id = request.args.get('box_id', type=int)
    if not box_id:
        return jsonify({'error': 'box_id parameter required'}), 400

    rows = db.execute("""
        SELECT rt.id, rt.tube_id, rt.box_id, rt.row_pos, rt.col_pos,
               rt.species_id, s.banding_code, s.common_name, s.scientific_name,
               rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
               rt.wrmd_number, rt.vmth_number, rt.notes, rt.created_at, rt.updated_at
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        WHERE rt.box_id = ?
    """, (box_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/raptor/tubes', methods=['POST'])
def create_tube():
    db = get_db()
    data = request.get_json()

    required = ['box_id', 'row_pos', 'col_pos', 'species_id', 'collection_date']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    # Get species banding code
    species = db.execute(
        "SELECT id, banding_code FROM species WHERE id = ?",
        (data['species_id'],)
    ).fetchone()
    if not species:
        return jsonify({'error': 'Species not found'}), 404

    try:
        tube_id = generate_raptor_tube_id(
            db, species['banding_code'], species['id'], data['collection_date']
        )

        db.execute(
            """INSERT INTO raptor_tubes
               (tube_id, box_id, row_pos, col_pos, species_id, collection_date,
                age, sex, freeze_thaw_cycles, wrmd_number, vmth_number, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tube_id, data['box_id'], data['row_pos'], data['col_pos'],
             data['species_id'], data['collection_date'],
             data.get('age', ''), data.get('sex', ''),
             data.get('freeze_thaw_cycles', 0),
             data.get('wrmd_number', ''), data.get('vmth_number', ''),
             data.get('notes', ''))
        )
        db.commit()

        row_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        tube = db.execute("""
            SELECT rt.*, s.banding_code, s.common_name, s.scientific_name
            FROM raptor_tubes rt
            JOIN species s ON rt.species_id = s.id
            WHERE rt.id = ?
        """, (row_id,)).fetchone()
        return jsonify(dict(tube)), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>', methods=['PUT'])
def update_tube(tube_id):
    db = get_db()
    data = request.get_json()

    try:
        db.execute(
            """UPDATE raptor_tubes
               SET collection_date = ?, age = ?, sex = ?,
                   freeze_thaw_cycles = ?, wrmd_number = ?, vmth_number = ?,
                   notes = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (data.get('collection_date'), data.get('age', ''), data.get('sex', ''),
             data.get('freeze_thaw_cycles', 0),
             data.get('wrmd_number', ''), data.get('vmth_number', ''),
             data.get('notes', ''), tube_id)
        )
        db.commit()
        tube = db.execute("""
            SELECT rt.*, s.banding_code, s.common_name, s.scientific_name
            FROM raptor_tubes rt
            JOIN species s ON rt.species_id = s.id
            WHERE rt.id = ?
        """, (tube_id,)).fetchone()
        if not tube:
            return jsonify({'error': 'Tube not found'}), 404
        return jsonify(dict(tube))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>', methods=['DELETE'])
def delete_tube(tube_id):
    db = get_db()
    db.execute("DELETE FROM raptor_tubes WHERE id = ?", (tube_id,))
    db.commit()
    return jsonify({'success': True})


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>/thaw', methods=['PUT'])
def record_thaw(tube_id):
    """Increment freeze-thaw cycle count by 1."""
    db = get_db()
    db.execute(
        "UPDATE raptor_tubes SET freeze_thaw_cycles = freeze_thaw_cycles + 1, updated_at = datetime('now') WHERE id = ?",
        (tube_id,)
    )
    db.commit()
    tube = db.execute("""
        SELECT rt.*, s.banding_code, s.common_name, s.scientific_name
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        WHERE rt.id = ?
    """, (tube_id,)).fetchone()
    if not tube:
        return jsonify({'error': 'Tube not found'}), 404
    return jsonify(dict(tube))


@raptor_bp.route('/api/raptor/search')
def search_tubes():
    db = get_db()
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    rows = db.execute("""
        SELECT rt.id, rt.tube_id, rt.box_id, rt.row_pos, rt.col_pos,
               s.banding_code, s.common_name, s.scientific_name,
               rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
               rt.wrmd_number, rt.vmth_number,
               b.label AS box_label, d.label AS drawer_label, r.label AS rack_label, sh.name AS shelf_name
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        JOIN boxes b ON rt.box_id = b.id
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        WHERE rt.tube_id LIKE ?
           OR s.common_name LIKE ?
           OR s.scientific_name LIKE ?
           OR s.banding_code LIKE ?
           OR rt.wrmd_number LIKE ?
           OR rt.vmth_number LIKE ?
        ORDER BY rt.tube_id
        LIMIT 50
    """, (f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%')).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/raptor/lookup/<tube_id_str>')
def lookup_by_tube_id(tube_id_str):
    """Look up a tube by its string ID (e.g., RTHA26001)."""
    db = get_db()
    tube = db.execute("""
        SELECT rt.*, s.banding_code, s.common_name, s.scientific_name,
               b.label AS box_label, d.label AS drawer_label, r.label AS rack_label, sh.name AS shelf_name
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        JOIN boxes b ON rt.box_id = b.id
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        WHERE rt.tube_id = ?
    """, (tube_id_str.upper(),)).fetchone()
    if not tube:
        return jsonify({'error': 'Tube not found'}), 404
    return jsonify(dict(tube))


@raptor_bp.route('/api/species')
def list_species():
    db = get_db()
    rows = db.execute(
        "SELECT id, common_name, scientific_name, banding_code FROM species ORDER BY common_name"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/species', methods=['POST'])
def create_species():
    db = get_db()
    data = request.get_json()
    required = ['common_name', 'scientific_name', 'banding_code']
    for field in required:
        if field not in data or not data[field].strip():
            return jsonify({'error': f'{field} is required'}), 400
    try:
        db.execute(
            "INSERT INTO species (common_name, scientific_name, banding_code) VALUES (?, ?, ?)",
            (data['common_name'].strip(), data['scientific_name'].strip(),
             data['banding_code'].strip().upper())
        )
        db.commit()
        species_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return jsonify({'id': species_id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400
