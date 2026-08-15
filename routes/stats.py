"""Statistics API endpoints."""

from flask import Blueprint, jsonify

from db import get_db
from services.stats_service import get_freezer_stats, get_raptor_stats, get_research_stats

stats_bp = Blueprint('stats', __name__)


@stats_bp.route('/api/stats/raptor')
def raptor_stats():
    return jsonify(get_raptor_stats(get_db()))


@stats_bp.route('/api/stats/research')
def research_stats():
    return jsonify(get_research_stats(get_db()))


@stats_bp.route('/api/stats/freezer')
def freezer_stats():
    return jsonify(get_freezer_stats(get_db()))
