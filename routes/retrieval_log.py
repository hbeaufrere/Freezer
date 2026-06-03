"""Retrieval log API endpoints."""

from flask import Blueprint, jsonify, request

from db import get_db
from auth import require_login, require_role, current_user

retrieval_log_bp = Blueprint('retrieval_log', __name__)


def _allowed_sections_for_user():
    """Which sections the current user is allowed to see entries from."""
    user = current_user()
    if not user:
        return []
    role = user['role']
    if role in ('admin', 'both'):
        return ['research', 'raptor']
    if role == 'raptor':
        return ['raptor']
    if role == 'clipr':
        return ['research']
    return []


@retrieval_log_bp.route('/api/retrieval-log')
@require_login
def list_log():
    """Return retrieval log entries with optional filters."""
    db = get_db()

    allowed = _allowed_sections_for_user()
    if not allowed:
        return jsonify({'entries': [], 'total': 0, 'limit': 0, 'offset': 0})

    section = request.args.get('section', '').strip()
    action = request.args.get('action', '').strip()
    q = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))

    conditions = []
    params = []

    # Always scope to sections the user can access
    if section in ('research', 'raptor') and section in allowed:
        conditions.append('section = %s')
        params.append(section)
    else:
        placeholders = ','.join(['%s'] * len(allowed))
        conditions.append(f'section IN ({placeholders})')
        params.extend(allowed)

    if action in ('removed', 'thawed'):
        conditions.append('action = %s')
        params.append(action)

    if q:
        conditions.append('(tube_identifier ILIKE %s OR retrieved_by ILIKE %s OR purpose ILIKE %s)')
        pattern = f'%{q}%'
        params.extend([pattern, pattern, pattern])

    where_clause = 'WHERE ' + ' AND '.join(conditions)

    rows = db.execute(
        f"""SELECT id, section, tube_identifier, tube_info, action,
                   retrieved_by, purpose, timestamp
            FROM retrieval_log
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s""",
        params + [limit, offset]
    ).fetchall()

    total = db.execute(
        f"SELECT COUNT(*) AS c FROM retrieval_log {where_clause}",
        params
    ).fetchone()['c']

    return jsonify({
        'entries': [dict(r) for r in rows],
        'total': total,
        'limit': limit,
        'offset': offset,
    })


@retrieval_log_bp.route('/api/retrieval-log/<int:entry_id>', methods=['DELETE'])
@require_role('admin')
def delete_log_entry(entry_id):
    db = get_db()
    db.execute("DELETE FROM retrieval_log WHERE id = %s", (entry_id,))
    db.commit()
    return jsonify({'success': True})


def log_retrieval(section, tube_identifier, tube_info, action, retrieved_by, purpose):
    """Helper called from raptor/research routes when a tube is removed or thawed."""
    user = current_user()
    user_id = user['id'] if user else None
    if not retrieved_by:
        retrieved_by = (user['full_name'] or user['email']) if user else None
    get_db().execute(
        """INSERT INTO retrieval_log
           (section, tube_identifier, tube_info, action, retrieved_by, purpose, user_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (section, tube_identifier, tube_info, action, retrieved_by, purpose, user_id)
    )
