"""Authentication & authorization helpers.

- Password hashing with bcrypt (via passlib).
- Temporary-password generation for admin-created accounts.
- Decorators: @require_login, @require_role.
- `current_user()` loads the active user once per request and caches on `g`.
"""

import secrets
import string
from functools import wraps

from flask import g, session, request, jsonify, redirect, url_for, render_template
from passlib.hash import bcrypt

from db import get_db


# ---------- password helpers ----------

_TEMP_PW_ALPHABET = string.ascii_letters + string.digits


def hash_password(plaintext: str) -> str:
    return bcrypt.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.verify(plaintext, hashed)
    except (ValueError, TypeError):
        return False


def generate_temp_password(length: int = 12) -> str:
    """Cryptographically random alphanumeric password."""
    return ''.join(secrets.choice(_TEMP_PW_ALPHABET) for _ in range(length))


# ---------- current user ----------

def current_user():
    """Return the authenticated user (dict) for this request, or None."""
    if hasattr(g, 'user'):
        return g.user

    user_id = session.get('user_id')
    if not user_id:
        g.user = None
        return None

    row = get_db().execute(
        """SELECT id, email, full_name, role, must_change_password, is_active
           FROM users WHERE id = %s""",
        (user_id,)
    ).fetchone()

    g.user = row if row and row['is_active'] else None
    if g.user is None:
        session.clear()
    return g.user


def login_user(user_row):
    session.clear()
    session['user_id'] = user_row['id']
    session.permanent = True


def logout_user():
    session.clear()


# ---------- decorators ----------

def _wants_json():
    return request.is_json or request.path.startswith('/api/')


def require_login(f):
    """Require an authenticated, active user.

    If the user must change their password, redirect them to /change-password
    (or return 403 for API calls) — except for the change-password and logout
    endpoints themselves.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user:
            if _wants_json():
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('auth.login'))

        # Force password change on first login
        if user['must_change_password']:
            allowed = {'auth.change_password', 'auth.do_change_password', 'auth.logout'}
            if request.endpoint not in allowed:
                if _wants_json():
                    return jsonify({'error': 'Password change required'}), 403
                return redirect(url_for('auth.change_password'))

        return f(*args, **kwargs)
    return decorated


def require_role(*allowed_roles):
    """Allow access if the user's role grants any of the allowed roles.

    Rules:
      - 'admin' always passes.
      - 'both' grants access to anything that allows 'raptor' or 'clipr'.
      - Otherwise the user's role must be in allowed_roles.
    """
    allowed = set(allowed_roles)

    def decorator(f):
        @wraps(f)
        @require_login
        def decorated(*args, **kwargs):
            role = current_user()['role']
            permitted = (
                role == 'admin'
                or role in allowed
                or (role == 'both' and ({'raptor', 'clipr'} & allowed))
            )
            if not permitted:
                if _wants_json():
                    return jsonify({'error': 'Forbidden'}), 403
                return render_template('forbidden.html'), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def user_can_access_section(section: str) -> bool:
    """Return True if the current user may access raptor/research data."""
    user = current_user()
    if not user:
        return False
    role = user['role']
    if role == 'admin' or role == 'both':
        return True
    if section == 'raptor' and role == 'raptor':
        return True
    if section == 'research' and role == 'clipr':
        return True
    return False
