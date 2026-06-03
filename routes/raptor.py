"""Raptor biobank tube CRUD endpoints with auto-ID generation."""

from flask import Blueprint, jsonify, request

from db import get_db
from auth import require_role
from services.id_generator import generate_raptor_tube_id
from routes.retrieval_log import log_retrieval

raptor_bp = Blueprint('raptor', __name__)


def _tube_location(db, tube):
    row = db.execute("""
        SELECT b.label AS box_label, d.label AS drawer_label,
               r.label AS rack_label, sh.name AS shelf_name
        FROM boxes b
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        WHERE b.id = %s
    """, (tube['box_id'],)).fetchone()
    if not row:
        return f"Position {tube['row_pos']},{tube['col_pos']}"
    return (f"{row['shelf_name']} / {row['rack_label']} / {row['drawer_label']} / "
            f"{row['box_label']} / {tube['row_pos']},{tube['col_pos']}")


def _fetch_raptor_tube(db, row_id):
    return db.execute("""
        SELECT rt.id, rt.tube_id, rt.box_id, rt.row_pos, rt.col_pos,
               rt.species_id, rt.collection_date, rt.age, rt.sex,
               rt.freeze_thaw_cycles, rt.wrmd_number, rt.vmth_number,
               rt.notes, rt.created_at, rt.updated_at,
               s.banding_code, s.common_name, s.scientific_name
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        WHERE rt.id = %s
    """, (row_id,)).fetchone()


@raptor_bp.route('/api/raptor/tubes')
@require_role('raptor')
def list_tubes():
    box_id = request.args.get('box_id', type=int)
    if not box_id:
        return jsonify({'error': 'box_id parameter required'}), 400

    rows = get_db().execute("""
        SELECT rt.id, rt.tube_id, rt.box_id, rt.row_pos, rt.col_pos,
               rt.species_id, s.banding_code, s.common_name, s.scientific_name,
               rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
               rt.wrmd_number, rt.vmth_number, rt.notes, rt.created_at, rt.updated_at
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        WHERE rt.box_id = %s
    """, (box_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/raptor/tubes', methods=['POST'])
@require_role('raptor')
def create_tube():
    db = get_db()
    data = request.get_json()

    required = ['box_id', 'row_pos', 'col_pos', 'species_id', 'collection_date']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    species = db.execute(
        "SELECT id, banding_code FROM species WHERE id = %s",
        (data['species_id'],)
    ).fetchone()
    if not species:
        return jsonify({'error': 'Species not found'}), 404

    num_tubes = data.get('num_tubes', 1)
    if not isinstance(num_tubes, int) or num_tubes < 1 or num_tubes > 20:
        return jsonify({'error': 'num_tubes must be between 1 and 20'}), 400

    try:
        base_tube_id = generate_raptor_tube_id(
            db, species['banding_code'], species['id'], data['collection_date']
        )

        if num_tubes == 1:
            row_id = db.execute(
                """INSERT INTO raptor_tubes
                   (tube_id, box_id, row_pos, col_pos, species_id, collection_date,
                    age, sex, freeze_thaw_cycles, wrmd_number, vmth_number, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (base_tube_id, data['box_id'], data['row_pos'], data['col_pos'],
                 data['species_id'], data['collection_date'],
                 data.get('age', ''), data.get('sex', ''),
                 data.get('freeze_thaw_cycles', 0),
                 data.get('wrmd_number', ''), data.get('vmth_number', ''),
                 data.get('notes', ''))
            ).fetchone()['id']
            tube = _fetch_raptor_tube(db, row_id)
            db.commit()
            return jsonify(dict(tube)), 201

        # Multi-tube path: find empty positions in the box
        box = db.execute(
            "SELECT grid_rows, grid_cols FROM boxes WHERE id = %s",
            (data['box_id'],)
        ).fetchone()
        if not box:
            return jsonify({'error': 'Box not found'}), 404

        occupied = set()
        for row in db.execute(
            "SELECT row_pos, col_pos FROM raptor_tubes WHERE box_id = %s",
            (data['box_id'],)
        ).fetchall():
            occupied.add((row['row_pos'], row['col_pos']))

        start_row, start_col = data['row_pos'], data['col_pos']
        empty_positions = []
        rows, cols = box['grid_rows'], box['grid_cols']
        for r in range(1, rows + 1):
            for c in range(1, cols + 1):
                if (r, c) < (start_row, start_col):
                    continue
                if (r, c) not in occupied:
                    empty_positions.append((r, c))
                if len(empty_positions) >= num_tubes:
                    break
            if len(empty_positions) >= num_tubes:
                break
        if len(empty_positions) < num_tubes:
            for r in range(1, rows + 1):
                for c in range(1, cols + 1):
                    if (r, c) >= (start_row, start_col):
                        break
                    if (r, c) not in occupied:
                        empty_positions.append((r, c))
                    if len(empty_positions) >= num_tubes:
                        break
                if len(empty_positions) >= num_tubes:
                    break

        if len(empty_positions) < num_tubes:
            return jsonify({
                'error': f'Not enough empty positions. Need {num_tubes}, found {len(empty_positions)}.'
            }), 400

        created_tubes = []
        for i, (r, c) in enumerate(empty_positions[:num_tubes]):
            tube_id = f"{base_tube_id}-{i + 1}"
            row_id = db.execute(
                """INSERT INTO raptor_tubes
                   (tube_id, box_id, row_pos, col_pos, species_id, collection_date,
                    age, sex, freeze_thaw_cycles, wrmd_number, vmth_number, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (tube_id, data['box_id'], r, c,
                 data['species_id'], data['collection_date'],
                 data.get('age', ''), data.get('sex', ''),
                 data.get('freeze_thaw_cycles', 0),
                 data.get('wrmd_number', ''), data.get('vmth_number', ''),
                 data.get('notes', ''))
            ).fetchone()['id']
            created_tubes.append(dict(_fetch_raptor_tube(db, row_id)))

        db.commit()
        return jsonify({'tubes': created_tubes}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>', methods=['PUT'])
@require_role('raptor')
def update_tube(tube_id):
    db = get_db()
    data = request.get_json()

    try:
        db.execute(
            """UPDATE raptor_tubes
               SET collection_date = %s, age = %s, sex = %s,
                   freeze_thaw_cycles = %s, wrmd_number = %s, vmth_number = %s,
                   notes = %s, updated_at = now()
               WHERE id = %s""",
            (data.get('collection_date'), data.get('age', ''), data.get('sex', ''),
             data.get('freeze_thaw_cycles', 0),
             data.get('wrmd_number', ''), data.get('vmth_number', ''),
             data.get('notes', ''), tube_id)
        )
        tube = _fetch_raptor_tube(db, tube_id)
        if not tube:
            db.rollback()
            return jsonify({'error': 'Tube not found'}), 404
        db.commit()
        return jsonify(dict(tube))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>', methods=['DELETE'])
@require_role('raptor')
def delete_tube(tube_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    retrieved_by = (data.get('retrieved_by') or '').strip() or None
    purpose = (data.get('purpose') or '').strip() or None

    tube = db.execute(
        "SELECT id, tube_id, box_id, row_pos, col_pos FROM raptor_tubes WHERE id = %s",
        (tube_id,)
    ).fetchone()
    if tube:
        log_retrieval('raptor', tube['tube_id'], _tube_location(db, tube),
                      'removed', retrieved_by, purpose)

    db.execute("DELETE FROM raptor_tubes WHERE id = %s", (tube_id,))
    db.commit()
    return jsonify({'success': True})


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>/thaw', methods=['PUT'])
@require_role('raptor')
def record_thaw(tube_id):
    """Increment freeze-thaw cycle count by 1 and log the retrieval."""
    db = get_db()
    data = request.get_json(silent=True) or {}
    retrieved_by = (data.get('retrieved_by') or '').strip() or None
    purpose = (data.get('purpose') or '').strip() or None

    raw = db.execute(
        "SELECT id, tube_id, box_id, row_pos, col_pos FROM raptor_tubes WHERE id = %s",
        (tube_id,)
    ).fetchone()
    if not raw:
        return jsonify({'error': 'Tube not found'}), 404

    db.execute(
        "UPDATE raptor_tubes SET freeze_thaw_cycles = freeze_thaw_cycles + 1, updated_at = now() WHERE id = %s",
        (tube_id,)
    )
    log_retrieval('raptor', raw['tube_id'], _tube_location(db, raw),
                  'thawed', retrieved_by, purpose)

    tube = _fetch_raptor_tube(db, tube_id)
    db.commit()
    return jsonify(dict(tube))


@raptor_bp.route('/api/raptor/search')
@require_role('raptor')
def search_tubes():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    pattern = f'%{q}%'
    rows = get_db().execute("""
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
        WHERE rt.tube_id ILIKE %s
           OR s.common_name ILIKE %s
           OR s.scientific_name ILIKE %s
           OR s.banding_code ILIKE %s
           OR rt.wrmd_number ILIKE %s
           OR rt.vmth_number ILIKE %s
        ORDER BY rt.tube_id
        LIMIT 50
    """, (pattern, pattern, pattern, pattern, pattern, pattern)).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/raptor/lookup/<tube_id_str>')
@require_role('raptor')
def lookup_by_tube_id(tube_id_str):
    """Look up a tube by its string ID (e.g., RTHA26001)."""
    tube = get_db().execute("""
        SELECT rt.*, s.banding_code, s.common_name, s.scientific_name,
               b.label AS box_label, d.label AS drawer_label, r.label AS rack_label, sh.name AS shelf_name
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        JOIN boxes b ON rt.box_id = b.id
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        WHERE rt.tube_id = %s
    """, (tube_id_str.upper(),)).fetchone()
    if not tube:
        return jsonify({'error': 'Tube not found'}), 404
    return jsonify(dict(tube))


@raptor_bp.route('/api/species')
@require_role('raptor', 'clipr')
def list_species():
    rows = get_db().execute(
        "SELECT id, common_name, scientific_name, banding_code FROM species ORDER BY common_name"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/species', methods=['POST'])
@require_role('raptor')
def create_species():
    db = get_db()
    data = request.get_json()
    required = ['common_name', 'scientific_name', 'banding_code']
    for field in required:
        if field not in data or not data[field].strip():
            return jsonify({'error': f'{field} is required'}), 400
    try:
        new_id = db.execute(
            "INSERT INTO species (common_name, scientific_name, banding_code) VALUES (%s, %s, %s) RETURNING id",
            (data['common_name'].strip(), data['scientific_name'].strip(),
             data['banding_code'].strip().upper())
        ).fetchone()['id']
        db.commit()
        return jsonify({'id': new_id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400
