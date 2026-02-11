#!/usr/bin/env python3
"""Biorepository Freezer Management System - Flask Application."""

import os
import sqlite3
from flask import Flask, g, render_template

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
    app.teardown_appcontext(close_db)

    # Register API blueprints
    from routes.freezer import freezer_bp
    from routes.research import research_bp
    from routes.raptor import raptor_bp
    from routes.stats import stats_bp
    from routes.export import export_bp

    app.register_blueprint(freezer_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(raptor_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(export_bp)

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

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
