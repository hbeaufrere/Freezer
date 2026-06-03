"""Statistics API endpoints."""

from flask import Blueprint, jsonify

from db import get_db
from auth import require_login, require_role
from services.stats_service import get_raptor_stats, get_research_stats, get_freezer_stats

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats/raptor')
@require_role('raptor')
def raptor_stats():
    return jsonify(get_raptor_stats(get_db()))


@stats_bp.route('/api/stats/research')
@require_role('clipr')
def research_stats():
    return jsonify(get_research_stats(get_db()))


@stats_bp.route('/api/stats/freezer')
@require_login
def freezer_stats():
    return jsonify(get_freezer_stats(get_db()))
