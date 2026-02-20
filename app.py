#!/usr/bin/env python3
"""Biorepository Freezer Management System - Flask Application."""

import os
import sqlite3
from flask import Flask, g, render_template, session, redirect, url_for, request

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'freezer.db')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def create_app():
    app = Flask(__name__)
    app.config['DATABASE'] = DATABASE
    app.secret_key = os.environ.get('SECRET_KEY', 'freezer-default-secret-change-me')
    app.teardown_appcontext(close_db)

    # Auto-apply database migrations on startup (idempotent)
    if os.path.exists(DATABASE):
        from migrate_taxonomy_and_racks import migrate
        migrate()

    # Password for simple auth (set via environment variable)
    lab_password = os.environ.get('FREEZER_PASSWORD', 'changeme')

    # Register API blueprints
    from routes.freezer import freezer_bp
    from routes.research import research_bp
    from routes.raptor import raptor_bp
    from routes.stats import stats_bp
    from routes.export import export_bp
    from routes.retrieval_log import retrieval_log_bp

    app.register_blueprint(freezer_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(raptor_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(retrieval_log_bp)

    # Disable browser caching for all API responses
    @app.after_request
    def no_cache_api(response):
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    # Authentication
    @app.before_request
    def require_login():
        allowed = ('login', 'static')
        if request.endpoint and request.endpoint in allowed:
            return
        if not session.get('authenticated'):
            return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        error = None
        if request.method == 'POST':
            if request.form.get('password') == lab_password:
                session['authenticated'] = True
                return redirect(url_for('index'))
            error = 'Incorrect password.'
        return render_template('login.html', error=error)

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    # Page routes
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

    @app.route('/retrieval-log')
    def retrieval_log_page():
        return render_template('retrieval_log.html')

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True, port=5000)
