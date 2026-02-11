"""Statistics API endpoints."""

from flask import Blueprint, jsonify
from services.stats_service import get_raptor_stats, get_research_stats, get_freezer_stats

stats_bp = Blueprint('stats', __name__)


def get_db():
    from app import get_db as _get_db
    return _get_db()


@stats_bp.route('/api/stats/raptor')
def raptor_stats():
    return jsonify(get_raptor_stats(get_db()))


@stats_bp.route('/api/stats/research')
def research_stats():
    return jsonify(get_research_stats(get_db()))


@stats_bp.route('/api/stats/freezer')
def freezer_stats():
    return jsonify(get_freezer_stats(get_db()))
