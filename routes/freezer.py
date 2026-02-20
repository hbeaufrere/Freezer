"""Freezer structure API endpoints (shelves, racks, drawers, boxes)."""

from flask import Blueprint, jsonify, request

freezer_bp = Blueprint('freezer', __name__)


def get_db():
    from app import get_db as _get_db
    return _get_db()


@freezer_bp.route('/api/freezer')
def get_freezer():
    """Full freezer structure with nested shelves → racks → drawers → boxes and occupancy counts."""
    db = get_db()

    shelves = db.execute(
        "SELECT id, name, position, section FROM shelves ORDER BY position"
    ).fetchall()

    result = []
    for shelf in shelves:
        shelf_data = dict(shelf)
        racks = db.execute(
            "SELECT id, position, label, designation, name FROM racks WHERE shelf_id = ? ORDER BY position",
            (shelf['id'],)
        ).fetchall()

        shelf_data['racks'] = []
        for rack in racks:
            rack_data = dict(rack)
            drawers = db.execute(
                "SELECT id, position, label, name FROM drawers WHERE rack_id = ? ORDER BY position",
                (rack['id'],)
            ).fetchall()

            rack_data['drawers'] = []
            for drawer in drawers:
                drawer_data = dict(drawer)
                boxes = db.execute("""
                    SELECT b.id, b.position, b.label, b.grid_rows, b.grid_cols, b.section,
                           COALESCE(rc.cnt, 0) + COALESCE(rp.cnt, 0) AS occupied,
                           b.grid_rows * b.grid_cols AS capacity
                    FROM boxes b
                    LEFT JOIN (SELECT box_id, COUNT(*) AS cnt FROM research_tubes GROUP BY box_id) rc ON rc.box_id = b.id
                    LEFT JOIN (SELECT box_id, COUNT(*) AS cnt FROM raptor_tubes GROUP BY box_id) rp ON rp.box_id = b.id
                    WHERE b.drawer_id = ?
                    ORDER BY b.position
                """, (drawer['id'],)).fetchall()

                drawer_data['boxes'] = [dict(b) for b in boxes]
                rack_data['drawers'].append(drawer_data)

            shelf_data['racks'].append(rack_data)
        result.append(shelf_data)

    return jsonify(result)


@freezer_bp.route('/api/shelves')
def list_shelves():
    db = get_db()
    rows = db.execute("SELECT id, name, position, section FROM shelves ORDER BY position").fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/shelves/<int:shelf_id>/racks')
def list_racks(shelf_id):
    db = get_db()
    rows = db.execute(
        "SELECT id, shelf_id, position, label, designation, name FROM racks WHERE shelf_id = ? ORDER BY position",
        (shelf_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/racks/<int:rack_id>', methods=['PUT'])
def update_rack(rack_id):
    db = get_db()
    data = request.get_json()
    try:
        db.execute(
            "UPDATE racks SET name = ? WHERE id = ?",
            (data.get('name', ''), rack_id)
        )
        db.commit()
        rack = db.execute(
            "SELECT id, shelf_id, position, label, designation, name FROM racks WHERE id = ?",
            (rack_id,)
        ).fetchone()
        if not rack:
            return jsonify({'error': 'Rack not found'}), 404
        return jsonify(dict(rack))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@freezer_bp.route('/api/racks/<int:rack_id>/drawers')
def list_drawers(rack_id):
    db = get_db()
    rows = db.execute(
        "SELECT id, rack_id, position, label, name FROM drawers WHERE rack_id = ? ORDER BY position",
        (rack_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/drawers/<int:drawer_id>', methods=['PUT'])
def update_drawer(drawer_id):
    db = get_db()
    data = request.get_json()
    try:
        db.execute(
            "UPDATE drawers SET name = ? WHERE id = ?",
            (data.get('name', '') or None, drawer_id)
        )
        db.commit()
        drawer = db.execute(
            "SELECT id, rack_id, position, label, name FROM drawers WHERE id = ?",
            (drawer_id,)
        ).fetchone()
        if not drawer:
            return jsonify({'error': 'Drawer not found'}), 404
        return jsonify(dict(drawer))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@freezer_bp.route('/api/drawers/<int:drawer_id>/boxes')
def list_boxes(drawer_id):
    db = get_db()
    rows = db.execute("""
        SELECT b.id, b.position, b.label, b.grid_rows, b.grid_cols, b.section,
               COALESCE(rc.cnt, 0) + COALESCE(rp.cnt, 0) AS occupied,
               b.grid_rows * b.grid_cols AS capacity
        FROM boxes b
        LEFT JOIN (SELECT box_id, COUNT(*) AS cnt FROM research_tubes GROUP BY box_id) rc ON rc.box_id = b.id
        LEFT JOIN (SELECT box_id, COUNT(*) AS cnt FROM raptor_tubes GROUP BY box_id) rp ON rp.box_id = b.id
        WHERE b.drawer_id = ?
        ORDER BY b.position
    """, (drawer_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/boxes/<int:box_id>')
def get_box(box_id):
    """Get box details with all tube positions."""
    db = get_db()

    box = db.execute("""
        SELECT b.id, b.position, b.label, b.grid_rows, b.grid_cols, b.section,
               d.label AS drawer_label, r.label AS rack_label, r.designation AS rack_designation,
               r.name AS rack_name, sh.name AS shelf_name
        FROM boxes b
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        WHERE b.id = ?
    """, (box_id,)).fetchone()

    if not box:
        return jsonify({'error': 'Box not found'}), 404

    box_data = dict(box)

    if box['section'] == 'raptor':
        tubes = db.execute("""
            SELECT rt.id, rt.tube_id, rt.row_pos, rt.col_pos,
                   s.banding_code, s.common_name, s.scientific_name,
                   rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
                   rt.wrmd_number, rt.vmth_number, rt.notes
            FROM raptor_tubes rt
            JOIN species s ON rt.species_id = s.id
            WHERE rt.box_id = ?
        """, (box_id,)).fetchall()
    else:
        tubes = db.execute("""
            SELECT id, row_pos, col_pos, sample_id, description, date_stored
            FROM research_tubes
            WHERE box_id = ?
        """, (box_id,)).fetchall()

    box_data['tubes'] = [dict(t) for t in tubes]
    return jsonify(box_data)


@freezer_bp.route('/api/boxes', methods=['POST'])
def create_box():
    db = get_db()
    data = request.get_json()
    try:
        db.execute(
            "INSERT INTO boxes (drawer_id, position, label, grid_rows, grid_cols, section) VALUES (?, ?, ?, ?, ?, ?)",
            (data['drawer_id'], data['position'], data.get('label', ''),
             data.get('grid_rows', 10), data.get('grid_cols', 10), data.get('section', 'research'))
        )
        db.commit()
        return jsonify({'id': db.execute("SELECT last_insert_rowid()").fetchone()[0]}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@freezer_bp.route('/api/boxes/<int:box_id>', methods=['PUT'])
def update_box(box_id):
    db = get_db()
    data = request.get_json()
    try:
        db.execute(
            "UPDATE boxes SET label = ?, grid_rows = ?, grid_cols = ? WHERE id = ?",
            (data.get('label'), data.get('grid_rows', 10), data.get('grid_cols', 10), box_id)
        )
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@freezer_bp.route('/api/boxes/<int:box_id>', methods=['DELETE'])
def delete_box(box_id):
    db = get_db()
    # Check if box has tubes
    research_count = db.execute("SELECT COUNT(*) FROM research_tubes WHERE box_id = ?", (box_id,)).fetchone()[0]
    raptor_count = db.execute("SELECT COUNT(*) FROM raptor_tubes WHERE box_id = ?", (box_id,)).fetchone()[0]
    if research_count + raptor_count > 0:
        return jsonify({'error': 'Cannot delete box with tubes in it'}), 400
    db.execute("DELETE FROM boxes WHERE id = ?", (box_id,))
    db.commit()
    return jsonify({'success': True})
