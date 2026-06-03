"""Freezer structure API endpoints (shelves, racks, drawers, boxes)."""

from flask import Blueprint, jsonify, request

from db import get_db
from auth import require_login, require_role, user_can_access_section

freezer_bp = Blueprint('freezer', __name__)


@freezer_bp.route('/api/freezer')
@require_login
def get_freezer():
    """Full freezer structure with nested shelves -> racks -> drawers -> boxes and occupancy counts."""
    db = get_db()

    shelves = db.execute(
        "SELECT id, name, position, section FROM shelves ORDER BY position"
    ).fetchall()

    result = []
    for shelf in shelves:
        shelf_data = dict(shelf)
        racks = db.execute(
            "SELECT id, position, label, designation FROM racks WHERE shelf_id = %s ORDER BY position",
            (shelf['id'],)
        ).fetchall()

        shelf_data['racks'] = []
        for rack in racks:
            rack_data = dict(rack)
            drawers = db.execute(
                "SELECT id, position, label FROM drawers WHERE rack_id = %s ORDER BY position",
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
                    WHERE b.drawer_id = %s
                    ORDER BY b.position
                """, (drawer['id'],)).fetchall()

                drawer_data['boxes'] = [dict(b) for b in boxes]
                rack_data['drawers'].append(drawer_data)

            shelf_data['racks'].append(rack_data)
        result.append(shelf_data)

    return jsonify(result)


@freezer_bp.route('/api/shelves')
@require_login
def list_shelves():
    rows = get_db().execute(
        "SELECT id, name, position, section FROM shelves ORDER BY position"
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/shelves/<int:shelf_id>/racks')
@require_login
def list_racks(shelf_id):
    rows = get_db().execute(
        "SELECT id, shelf_id, position, label, designation FROM racks WHERE shelf_id = %s ORDER BY position",
        (shelf_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/racks/<int:rack_id>/drawers')
@require_login
def list_drawers(rack_id):
    rows = get_db().execute(
        "SELECT id, rack_id, position, label FROM drawers WHERE rack_id = %s ORDER BY position",
        (rack_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/drawers/<int:drawer_id>/boxes')
@require_login
def list_boxes(drawer_id):
    rows = get_db().execute("""
        SELECT b.id, b.position, b.label, b.grid_rows, b.grid_cols, b.section,
               COALESCE(rc.cnt, 0) + COALESCE(rp.cnt, 0) AS occupied,
               b.grid_rows * b.grid_cols AS capacity
        FROM boxes b
        LEFT JOIN (SELECT box_id, COUNT(*) AS cnt FROM research_tubes GROUP BY box_id) rc ON rc.box_id = b.id
        LEFT JOIN (SELECT box_id, COUNT(*) AS cnt FROM raptor_tubes GROUP BY box_id) rp ON rp.box_id = b.id
        WHERE b.drawer_id = %s
        ORDER BY b.position
    """, (drawer_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@freezer_bp.route('/api/boxes/<int:box_id>')
@require_login
def get_box(box_id):
    """Get box details with all tube positions (if the user can access that section)."""
    db = get_db()

    box = db.execute("""
        SELECT b.id, b.position, b.label, b.grid_rows, b.grid_cols, b.section,
               d.label AS drawer_label, r.label AS rack_label, r.designation AS rack_designation,
               sh.name AS shelf_name
        FROM boxes b
        JOIN drawers d ON b.drawer_id = d.id
        JOIN racks r ON d.rack_id = r.id
        JOIN shelves sh ON r.shelf_id = sh.id
        WHERE b.id = %s
    """, (box_id,)).fetchone()

    if not box:
        return jsonify({'error': 'Box not found'}), 404

    if not user_can_access_section(box['section']):
        return jsonify({'error': 'Forbidden for your role'}), 403

    box_data = dict(box)

    if box['section'] == 'raptor':
        tubes = db.execute("""
            SELECT rt.id, rt.tube_id, rt.row_pos, rt.col_pos,
                   s.banding_code, s.common_name, s.scientific_name,
                   rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
                   rt.wrmd_number, rt.vmth_number, rt.notes
            FROM raptor_tubes rt
            JOIN species s ON rt.species_id = s.id
            WHERE rt.box_id = %s
        """, (box_id,)).fetchall()
    else:
        tubes = db.execute("""
            SELECT id, row_pos, col_pos, sample_id, description, date_stored
            FROM research_tubes
            WHERE box_id = %s
        """, (box_id,)).fetchall()

    box_data['tubes'] = [dict(t) for t in tubes]
    return jsonify(box_data)


@freezer_bp.route('/api/boxes', methods=['POST'])
@require_role('admin')
def create_box():
    db = get_db()
    data = request.get_json()
    try:
        new_id = db.execute(
            """INSERT INTO boxes (drawer_id, position, label, grid_rows, grid_cols, section)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (data['drawer_id'], data['position'], data.get('label', ''),
             data.get('grid_rows', 10), data.get('grid_cols', 10), data.get('section', 'research'))
        ).fetchone()['id']
        db.commit()
        return jsonify({'id': new_id}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@freezer_bp.route('/api/boxes/<int:box_id>', methods=['PUT'])
@require_role('admin')
def update_box(box_id):
    db = get_db()
    data = request.get_json()
    try:
        db.execute(
            "UPDATE boxes SET label = %s, grid_rows = %s, grid_cols = %s WHERE id = %s",
            (data.get('label'), data.get('grid_rows', 10), data.get('grid_cols', 10), box_id)
        )
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400


@freezer_bp.route('/api/boxes/<int:box_id>', methods=['DELETE'])
@require_role('admin')
def delete_box(box_id):
    db = get_db()
    research_count = db.execute(
        "SELECT COUNT(*) AS c FROM research_tubes WHERE box_id = %s", (box_id,)
    ).fetchone()['c']
    raptor_count = db.execute(
        "SELECT COUNT(*) AS c FROM raptor_tubes WHERE box_id = %s", (box_id,)
    ).fetchone()['c']
    if research_count + raptor_count > 0:
        return jsonify({'error': 'Cannot delete box with tubes in it'}), 400
    db.execute("DELETE FROM boxes WHERE id = %s", (box_id,))
    db.commit()
    return jsonify({'success': True})
