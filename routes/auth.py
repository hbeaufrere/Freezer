"""Authentication routes: login, logout, change-password."""

from flask import Blueprint, render_template, request, redirect, url_for, session

from db import get_db
from auth import (
    verify_password, hash_password,
    login_user, logout_user, current_user,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET'])
def login():
    if current_user():
        return redirect(url_for('pages.index'))
    return render_template('login.html', error=None)


@auth_bp.route('/login', methods=['POST'])
def do_login():
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''

    if not email or not password:
        return render_template('login.html', error='Email and password are required.'), 400

    db = get_db()
    user = db.execute(
        "SELECT id, email, password_hash, role, must_change_password, is_active FROM users WHERE LOWER(email) = %s",
        (email,)
    ).fetchone()

    if not user or not user['is_active'] or not verify_password(password, user['password_hash']):
        return render_template('login.html', error='Invalid email or password.'), 401

    db.execute("UPDATE users SET last_login_at = now() WHERE id = %s", (user['id'],))
    db.commit()

    login_user(user)
    if user['must_change_password']:
        return redirect(url_for('auth.change_password'))
    return redirect(url_for('pages.index'))


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET'])
def change_password():
    if not current_user():
        return redirect(url_for('auth.login'))
    return render_template('change_password.html', error=None, forced=current_user()['must_change_password'])


@auth_bp.route('/change-password', methods=['POST'])
def do_change_password():
    user = current_user()
    if not user:
        return redirect(url_for('auth.login'))

    current_pw = request.form.get('current_password') or ''
    new_pw = request.form.get('new_password') or ''
    confirm = request.form.get('confirm_password') or ''

    db = get_db()
    row = db.execute("SELECT password_hash FROM users WHERE id = %s", (user['id'],)).fetchone()

    error = None
    if not verify_password(current_pw, row['password_hash']):
        error = 'Current password is incorrect.'
    elif len(new_pw) < 8:
        error = 'New password must be at least 8 characters.'
    elif new_pw != confirm:
        error = 'New password and confirmation do not match.'

    if error:
        return render_template('change_password.html', error=error, forced=user['must_change_password']), 400

    db.execute(
        """UPDATE users
           SET password_hash = %s, must_change_password = FALSE, updated_at = now()
           WHERE id = %s""",
        (hash_password(new_pw), user['id'])
    )
    db.commit()

    # Refresh cached user
    session.pop('_flush_user', None)
    return redirect(url_for('pages.index'))
