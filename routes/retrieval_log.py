"""Retrieval log API endpoints."""

from flask import Blueprint, jsonify, request

retrieval_log_bp = Blueprint('retrieval_log', __name__)


def get_db():
    from app import get_db as _get_db
    return _get_db()


@retrieval_log_bp.route('/api/retrieval-log')
def list_log():
    """Return retrieval log entries with optional filters."""
    db = get_db()

    section = request.args.get('section', '').strip()
    action = request.args.get('action', '').strip()
    q = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 200)), 500)
    offset = int(request.args.get('offset', 0))

    conditions = []
    params = []

    if section in ('research', 'raptor'):
        conditions.append('section = ?')
        params.append(section)

    if action in ('removed', 'thawed'):
        conditions.append('action = ?')
        params.append(action)

    if q:
        conditions.append('(tube_identifier LIKE ? OR retrieved_by LIKE ? OR purpose LIKE ?)')
        params.extend([f'%{q}%', f'%{q}%', f'%{q}%'])

    where_clause = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''

    rows = db.execute(
        f"""SELECT id, section, tube_identifier, tube_info, action, retrieved_by, purpose, timestamp
            FROM retrieval_log
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset]
    ).fetchall()

    total = db.execute(
        f"SELECT COUNT(*) FROM retrieval_log {where_clause}",
        params
    ).fetchone()[0]

    return jsonify({
        'entries': [dict(r) for r in rows],
        'total': total,
        'limit': limit,
        'offset': offset
    })


@retrieval_log_bp.route('/api/retrieval-log/<int:entry_id>', methods=['DELETE'])
def delete_log_entry(entry_id):
    """Delete a single retrieval log entry by ID."""
    db = get_db()
    result = db.execute("DELETE FROM retrieval_log WHERE id = ?", (entry_id,))
    db.commit()
    if result.rowcount == 0:
        return jsonify({'error': 'Entry not found'}), 404
    return jsonify({'success': True})
