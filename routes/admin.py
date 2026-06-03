"""Admin user-management routes."""

from flask import Blueprint, render_template, request, jsonify

from db import get_db
from auth import (
    require_role, current_user,
    hash_password, generate_temp_password,
)
from services.email import send_temp_password
import config

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin/users')
@require_role('admin')
def users_page():
    return render_template('admin/users.html', role_labels=config.ROLE_LABELS, roles=config.ROLES)


@admin_bp.route('/api/admin/users')
@require_role('admin')
def list_users():
    rows = get_db().execute(
        """SELECT id, email, full_name, role, must_change_password, is_active,
                  created_at, last_login_at
           FROM users ORDER BY created_at DESC"""
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@admin_bp.route('/api/admin/users', methods=['POST'])
@require_role('admin')
def create_user():
    db = get_db()
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    full_name = (data.get('full_name') or '').strip() or None
    role = (data.get('role') or '').strip()

    if not email or '@' not in email:
        return jsonify({'error': 'Valid email required'}), 400
    if role not in config.ROLES:
        return jsonify({'error': f'Role must be one of: {", ".join(config.ROLES)}'}), 400

    existing = db.execute("SELECT id FROM users WHERE LOWER(email) = %s", (email,)).fetchone()
    if existing:
        return jsonify({'error': 'A user with that email already exists'}), 409

    temp_pw = generate_temp_password()

    try:
        new_id = db.execute(
            """INSERT INTO users (email, full_name, password_hash, role, must_change_password)
               VALUES (%s, %s, %s, %s, TRUE) RETURNING id""",
            (email, full_name, hash_password(temp_pw), role)
        ).fetchone()['id']
        db.commit()
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400

    try:
        send_temp_password(email, full_name or '', temp_pw, config.ROLE_LABELS.get(role, role))
        email_sent = True
        email_error = None
    except Exception as e:
        email_sent = False
        email_error = str(e)

    return jsonify({
        'id': new_id,
        'email': email,
        'role': role,
        'email_sent': email_sent,
        'email_error': email_error,
        # Surface the temp password to the admin as a fallback when email delivery fails
        'temp_password_fallback': temp_pw if not email_sent else None,
    }), 201


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['PATCH'])
@require_role('admin')
def update_user(user_id):
    db = get_db()
    data = request.get_json() or {}

    updates = []
    params = []
    if 'role' in data:
        if data['role'] not in config.ROLES:
            return jsonify({'error': f'Role must be one of: {", ".join(config.ROLES)}'}), 400
        updates.append('role = %s')
        params.append(data['role'])
    if 'is_active' in data:
        if user_id == current_user()['id'] and not data['is_active']:
            return jsonify({'error': "You can't deactivate your own account"}), 400
        updates.append('is_active = %s')
        params.append(bool(data['is_active']))
    if 'full_name' in data:
        updates.append('full_name = %s')
        params.append((data['full_name'] or '').strip() or None)

    if not updates:
        return jsonify({'error': 'No fields to update'}), 400

    updates.append('updated_at = now()')
    params.append(user_id)

    db.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = %s", params)
    db.commit()
    return jsonify({'success': True})


@admin_bp.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@require_role('admin')
def reset_password(user_id):
    db = get_db()
    user = db.execute(
        "SELECT id, email, full_name, role FROM users WHERE id = %s", (user_id,)
    ).fetchone()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    temp_pw = generate_temp_password()
    db.execute(
        """UPDATE users
           SET password_hash = %s, must_change_password = TRUE, updated_at = now()
           WHERE id = %s""",
        (hash_password(temp_pw), user_id)
    )
    db.commit()

    try:
        send_temp_password(
            user['email'], user['full_name'] or '', temp_pw,
            config.ROLE_LABELS.get(user['role'], user['role'])
        )
        email_sent = True
        email_error = None
    except Exception as e:
        email_sent = False
        email_error = str(e)

    return jsonify({
        'success': True,
        'email_sent': email_sent,
        'email_error': email_error,
        'temp_password_fallback': temp_pw if not email_sent else None,
    })


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_role('admin')
def delete_user(user_id):
    if user_id == current_user()['id']:
        return jsonify({'error': "You can't delete your own account"}), 400
    db = get_db()
    db.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()
    return jsonify({'success': True})
