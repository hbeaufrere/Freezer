"""Cron endpoints (called by Vercel's scheduler)."""

import hmac
from flask import Blueprint, jsonify, request

from db import get_db
import config

cron_bp = Blueprint('cron', __name__)


def _authorized() -> bool:
    """Vercel cron jobs send `Authorization: Bearer <CRON_SECRET>`."""
    if not config.CRON_SECRET:
        return True  # No secret configured -> assume local/dev
    auth_header = request.headers.get('Authorization', '')
    expected = f'Bearer {config.CRON_SECRET}'
    return hmac.compare_digest(auth_header, expected)


@cron_bp.route('/api/cron/keepalive')
def keepalive():
    """Touch the database so Supabase's free-tier pause timer resets."""
    if not _authorized():
        return jsonify({'error': 'Unauthorized'}), 401
    row = get_db().execute("SELECT now() AS ts").fetchone()
    return jsonify({'ok': True, 'now': row['ts'].isoformat()})
