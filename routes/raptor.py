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

    num_tubes = data.get('num_tubes', 1)
    if not isinstance(num_tubes, int) or num_tubes < 1 or num_tubes > 20:
        return jsonify({'error': 'num_tubes must be between 1 and 20'}), 400

    try:
        base_tube_id = generate_raptor_tube_id(
            db, species['banding_code'], species['id'], data['collection_date']
        )

        if num_tubes == 1:
            # Single tube — no suffix
            db.execute(
                """INSERT INTO raptor_tubes
                   (tube_id, box_id, row_pos, col_pos, species_id, collection_date,
                    age, sex, freeze_thaw_cycles, wrmd_number, vmth_number, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (base_tube_id, data['box_id'], data['row_pos'], data['col_pos'],
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
        else:
            # Multiple tubes — find empty positions in the box
            box = db.execute(
                "SELECT grid_rows, grid_cols FROM boxes WHERE id = ?",
                (data['box_id'],)
            ).fetchone()
            if not box:
                return jsonify({'error': 'Box not found'}), 404

            occupied = set()
            for row in db.execute(
                "SELECT row_pos, col_pos FROM raptor_tubes WHERE box_id = ?",
                (data['box_id'],)
            ).fetchall():
                occupied.add((row[0], row[1]))

            # Collect empty positions scanning left-to-right, top-to-bottom
            # starting from the clicked position
            start_row, start_col = data['row_pos'], data['col_pos']
            empty_positions = []
            rows, cols = box['grid_rows'], box['grid_cols']
            # First pass: from clicked position to end
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
            # Second pass: wrap around from beginning if needed
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
                db.execute(
                    """INSERT INTO raptor_tubes
                       (tube_id, box_id, row_pos, col_pos, species_id, collection_date,
                        age, sex, freeze_thaw_cycles, wrmd_number, vmth_number, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (tube_id, data['box_id'], r, c,
                     data['species_id'], data['collection_date'],
                     data.get('age', ''), data.get('sex', ''),
                     data.get('freeze_thaw_cycles', 0),
                     data.get('wrmd_number', ''), data.get('vmth_number', ''),
                     data.get('notes', ''))
                )
                row_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                tube = db.execute("""
                    SELECT rt.*, s.banding_code, s.common_name, s.scientific_name
                    FROM raptor_tubes rt
                    JOIN species s ON rt.species_id = s.id
                    WHERE rt.id = ?
                """, (row_id,)).fetchone()
                created_tubes.append(dict(tube))

            db.commit()
            return jsonify({'tubes': created_tubes}), 201
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
    data = request.get_json(silent=True) or {}
    retrieved_by = data.get('retrieved_by', '').strip()
    purpose = data.get('purpose', '').strip()

    tube = db.execute("""
        SELECT rt.*, b.label AS box_label, d.label AS drawer_label, r.label AS rack_label
        FROM raptor_tubes rt
        LEFT JOIN boxes b ON rt.box_id = b.id
        LEFT JOIN drawers d ON b.drawer_id = d.id
        LEFT JOIN racks r ON d.rack_id = r.id
        WHERE rt.id = ?
    """, (tube_id,)).fetchone()

    if tube:
        location = f"{tube['rack_label']}-{tube['drawer_label']}-{tube['box_label']}, Pos {tube['row_pos']},{tube['col_pos']}"
        # Log the removal before deleting
        db.execute(
            """INSERT INTO retrieval_log (section, tube_identifier, tube_info, action, retrieved_by, purpose)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ('raptor', tube['tube_id'], location, 'removed', retrieved_by, purpose)
        )

    db.execute("DELETE FROM raptor_tubes WHERE id = ?", (tube_id,))
    db.commit()
    return jsonify({'success': True})


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>/thaw', methods=['PUT'])
def record_thaw(tube_id):
    """Increment freeze-thaw cycle count by 1 and log the retrieval."""
    db = get_db()
    data = request.get_json(silent=True) or {}
    retrieved_by = data.get('retrieved_by', '').strip()
    purpose = data.get('purpose', '').strip()

    raw_tube = db.execute("""
        SELECT rt.*, b.label AS box_label, d.label AS drawer_label, r.label AS rack_label
        FROM raptor_tubes rt
        LEFT JOIN boxes b ON rt.box_id = b.id
        LEFT JOIN drawers d ON b.drawer_id = d.id
        LEFT JOIN racks r ON d.rack_id = r.id
        WHERE rt.id = ?
    """, (tube_id,)).fetchone()
    if not raw_tube:
        return jsonify({'error': 'Tube not found'}), 404

    db.execute(
        "UPDATE raptor_tubes SET freeze_thaw_cycles = freeze_thaw_cycles + 1, updated_at = datetime('now') WHERE id = ?",
        (tube_id,)
    )

    location = f"{raw_tube['rack_label']}-{raw_tube['drawer_label']}-{raw_tube['box_label']}, Pos {raw_tube['row_pos']},{raw_tube['col_pos']}"
    # Log the retrieval event
    db.execute(
        """INSERT INTO retrieval_log (section, tube_identifier, tube_info, action, retrieved_by, purpose)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ('raptor', raw_tube['tube_id'], location, 'thawed', retrieved_by, purpose)
    )

    db.commit()
    tube = db.execute("""
        SELECT rt.*, s.banding_code, s.common_name, s.scientific_name
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        WHERE rt.id = ?
    """, (tube_id,)).fetchone()
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
