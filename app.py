#!/usr/bin/env python3
"""Biorepository Freezer Management System.

Flask + PostgreSQL, deployed as a Vercel Function. Vercel looks for
a module-level ``app``, which is created at the bottom of this file.
"""

import hmac
import logging
import os
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask.json.provider import DefaultJSONProvider

from db import ApiError, close_db

try:  # Local development convenience; not installed in production.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

log = logging.getLogger(__name__)


def _required_env(name, hint):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f'{name} is not set. {hint}')
    return value


class IsoDateJSON(DefaultJSONProvider):
    """Emit ISO 8601 dates.

    Flask's default renders dates in HTTP format ("Wed, 15 Aug 2026 ..."),
    which the date inputs in the browser cannot read back.
    """

    @staticmethod
    def default(value):
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return DefaultJSONProvider.default(value)


def create_app():
    app = Flask(
        __name__,
        # Vercel serves everything under public/ straight from the CDN, so the
        # same files back both local development and production.
        static_folder='public/static',
        static_url_path='/static',
    )
    app.json = IsoDateJSON(app)

    app.secret_key = _required_env(
        'SECRET_KEY',
        "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'",
    )
    lab_password = _required_env(
        'FREEZER_PASSWORD',
        'Set it to the shared lab password in your Vercel environment variables.',
    )

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        # Vercel is HTTPS-only; allow plain HTTP just for local development.
        SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') != 'development',
        PERMANENT_SESSION_LIFETIME=timedelta(
            hours=int(os.environ.get('SESSION_HOURS', '12'))
        ),
        JSON_SORT_KEYS=False,
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
    )

    app.teardown_appcontext(close_db)

    from routes.export import export_bp
    from routes.freezer import freezer_bp
    from routes.raptor import raptor_bp
    from routes.research import research_bp
    from routes.retrieval import retrieval_bp
    from routes.stats import stats_bp

    for blueprint in (freezer_bp, research_bp, raptor_bp, stats_bp,
                      export_bp, retrieval_bp):
        app.register_blueprint(blueprint)

    # ------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------

    PUBLIC_ENDPOINTS = {'login', 'static', 'health'}

    @app.before_request
    def require_login():
        if request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if session.get('authenticated'):
            return None
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not signed in'}), 401
        return redirect(url_for('login', next=request.path))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            submitted = request.form.get('password', '')
            if hmac.compare_digest(submitted, lab_password):
                session.clear()
                session['authenticated'] = True
                session.permanent = True
                target = request.args.get('next', '')
                # Only ever redirect within this app.
                if not target.startswith('/') or target.startswith('//'):
                    target = url_for('index')
                return redirect(target)
            error = 'That password was not recognised.'
        return render_template('login.html', error=error)

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    # ------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/research')
    def research_page():
        return render_template('research.html')

    @app.route('/raptor')
    def raptor_page():
        return render_template('raptor.html')

    @app.route('/stats')
    def stats_page():
        return render_template('stats.html')

    @app.route('/retrievals')
    def retrievals_page():
        return render_template('retrievals.html')

    # Columns the code depends on, and the migration that adds each. Migrations
    # are applied by hand, so a forgotten one otherwise shows up as an
    # unexplained 500 on one page. This turns it into a named file to run.
    REQUIRED_SCHEMA = {
        ('raptor_tubes', 'sample_type'): '20260815000002_add_sample_type.sql',
        ('drawers', 'note'): '20260815000003_retrievals_and_drawer_notes.sql',
        ('retrievals', 'retrieved_by'): '20260815000003_retrievals_and_drawer_notes.sql',
    }

    @app.route('/api/health')
    def health():
        """Liveness probe: is the database reachable, and is its schema current?"""
        from db import get_db

        try:
            db = get_db()
            present = {
                (r['table_name'], r['column_name'])
                for r in db.execute(
                    """select table_name, column_name from information_schema.columns
                       where table_schema = 'public'"""
                ).fetchall()
            }
        except Exception:
            log.exception('Health check could not reach the database')
            return jsonify({'status': 'error', 'database': 'unreachable'}), 503

        missing = sorted({
            migration for key, migration in REQUIRED_SCHEMA.items() if key not in present
        })

        if missing:
            return jsonify({
                'status': 'error',
                'database': 'connected',
                'schema': 'out of date',
                'pending_migrations': missing,
                'detail': 'Run these files from migrations/ against the database, '
                          'oldest first.',
            }), 503

        return jsonify({'status': 'ok', 'database': 'connected', 'schema': 'current'})

    # ------------------------------------------------------------
    # Error handling — never leak schema details to the browser
    # ------------------------------------------------------------

    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        return jsonify({'error': exc.message}), exc.status

    @app.errorhandler(404)
    def handle_not_found(exc):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return render_template('error.html', code=404,
                               message='That page does not exist.'), 404

    @app.errorhandler(Exception)
    def handle_unexpected(exc):
        from werkzeug.exceptions import HTTPException

        if isinstance(exc, HTTPException):
            return exc
        log.exception('Unhandled error on %s %s', request.method, request.path)
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Something went wrong. Please try again.'}), 500
        return render_template('error.html', code=500,
                               message='Something went wrong on our side.'), 500

    return app


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), debug=True)
