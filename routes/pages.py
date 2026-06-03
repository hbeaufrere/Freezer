"""HTML page routes (templates only — data comes from the JSON APIs)."""

from flask import Blueprint, render_template, redirect, url_for

from auth import require_login, current_user

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
@require_login
def index():
    return render_template('index.html', user=current_user())


@pages_bp.route('/research')
@require_login
def research():
    return render_template('research.html', user=current_user())


@pages_bp.route('/raptor')
@require_login
def raptor():
    return render_template('raptor.html', user=current_user())


@pages_bp.route('/stats')
@require_login
def stats():
    return render_template('stats.html', user=current_user())


@pages_bp.route('/retrieval-log')
@require_login
def retrieval_log():
    return render_template('retrieval_log.html', user=current_user())
