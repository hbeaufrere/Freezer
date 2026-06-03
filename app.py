"""Biorepository Freezer Management System - Flask Application (Vercel build)."""

from datetime import timedelta
from flask import Flask

import config
from db import close_db


def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.permanent_session_lifetime = timedelta(days=14)
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    app.teardown_appcontext(close_db)

    # Blueprints
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.pages import pages_bp
    from routes.freezer import freezer_bp
    from routes.research import research_bp
    from routes.raptor import raptor_bp
    from routes.stats import stats_bp
    from routes.export import export_bp
    from routes.cron import cron_bp
    from routes.retrieval_log import retrieval_log_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(freezer_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(raptor_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(cron_bp)
    app.register_blueprint(retrieval_log_bp)

    @app.context_processor
    def inject_user():
        from auth import current_user
        return {'current_user': current_user()}

    return app


# Vercel imports `app` from this module.
app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
