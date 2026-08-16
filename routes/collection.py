"""Satellite collection sites — samples waiting to be moved to the -80.

The drop-off endpoint is deliberately public. Whoever is standing at the CRC
or VMTH freezer with a phone does not have the lab password, and asking for it
would defeat the point of a QR code on the door. The unguessable per-site
token in the URL is what stands in for authentication. What it protects is a
counter, not specimen records: the worst a bad actor can do is inflate a
number that the lab can reset, and every drop is attributable by time.
"""

import hmac

from flask import Blueprint, current_app, jsonify, render_template, request

from db import ApiError, get_db
from routes.support import as_int, json_body, one_or_404, require, text, write

collection_bp = Blueprint('collection', __name__)

MAX_PER_DROP = 500

_SITE_SUMMARY = """
    select s.id, s.code, s.name, s.location, s.position,
           coalesce(sum(d.sample_count) filter (where d.collected_at is null), 0) as pending_samples,
           count(d.id) filter (where d.collected_at is null) as pending_dropoffs,
           min(d.dropped_at) filter (where d.collected_at is null) as oldest_dropped_at,
           extract(day from now() - min(d.dropped_at)
                   filter (where d.collected_at is null))::int as oldest_age_days,
           max(d.collected_at) as last_collected_at
    from collection_sites s
    left join pending_dropoffs d on d.site_id = s.id
    group by s.id, s.code, s.name, s.location, s.position
    order by s.position, s.code
"""


def _find_site_by_token(db, token):
    """Look the site up by token, comparing in constant time.

    Postgres would happily do `where token = %s`, but that comparison is not
    constant time. The set of sites is two rows, so scanning them costs
    nothing and avoids leaking token prefixes through timing.
    """
    if not token or len(token) < 16:
        return None
    rows = db.execute('select id, code, name, location, token from collection_sites').fetchall()
    for row in rows:
        if hmac.compare_digest(row['token'], token):
            return row
    return None


# ------------------------------------------------------------
# Signed-in views
# ------------------------------------------------------------

@collection_bp.route('/api/collection-sites')
def list_sites():
    """Every satellite site with what is waiting there."""
    # The token is deliberately absent here — it is fetched only when someone
    # asks for the QR, so it is not sitting in every page's payload.
    rows = get_db().execute(_SITE_SUMMARY).fetchall()
    return jsonify([dict(r) for r in rows])


@collection_bp.route('/api/collection-sites/<int:site_id>/qr')
def site_qr(site_id):
    """The drop-off URL for this site, for printing a QR code."""
    row = one_or_404(
        get_db().execute(
            'select id, code, name, token from collection_sites where id = %s', (site_id,)
        ).fetchone(),
        'Site',
    )
    return jsonify({
        'id': row['id'],
        'code': row['code'],
        'name': row['name'],
        'drop_url': request.url_root.rstrip('/') + f'/drop/{row["token"]}',
    })


@collection_bp.route('/api/collection-sites/<int:site_id>/collect', methods=['POST'])
def collect_site(site_id):
    """Mark everything waiting at one site as collected.

    Per site on purpose: CRC and VMTH are separate trips.
    """
    db = get_db()
    data = request.get_json(silent=True) or {}

    one_or_404(
        db.execute('select id from collection_sites where id = %s', (site_id,)).fetchone(),
        'Site',
    )

    with write(db):
        result = db.execute(
            """update pending_dropoffs
               set collected_at = now(), collected_by = %s
               where site_id = %s and collected_at is null
               returning sample_count""",
            (text(data, 'collected_by') or None, site_id),
        ).fetchall()

    return jsonify({
        'collected_dropoffs': len(result),
        'collected_samples': sum(r['sample_count'] for r in result),
    })


@collection_bp.route('/api/collection-sites/<int:site_id>/dropoffs')
def site_dropoffs(site_id):
    """Recent drops at one site, newest first."""
    rows = get_db().execute(
        """select id, sample_count, dropped_at, dropped_by, note,
                  collected_at, collected_by
           from pending_dropoffs
           where site_id = %s
           order by dropped_at desc
           limit 50""",
        (site_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@collection_bp.route('/api/dropoffs/<int:dropoff_id>', methods=['DELETE'])
def delete_dropoff(dropoff_id):
    """Remove a mistaken drop entry."""
    db = get_db()
    with write(db):
        deleted = db.execute(
            'delete from pending_dropoffs where id = %s', (dropoff_id,)
        ).rowcount
    if not deleted:
        raise ApiError('Drop-off not found.', 404)
    return jsonify({'success': True})


# ------------------------------------------------------------
# Public drop-off, reached by scanning the QR on the freezer
# ------------------------------------------------------------

@collection_bp.route('/drop/<token>')
def dropoff_page(token):
    """The page the QR code opens. No login: see the module docstring."""
    site = _find_site_by_token(get_db(), token)
    if site is None:
        return render_template('dropoff.html', site=None, token=None), 404
    return render_template('dropoff.html', site=site, token=token)


@collection_bp.route('/api/drop/<token>', methods=['POST'])
def record_dropoff(token):
    db = get_db()
    site = _find_site_by_token(db, token)
    if site is None:
        raise ApiError('That drop-off link is not valid.', 404)

    data = json_body()
    require(data, 'sample_count')
    count = as_int(data, 'sample_count', minimum=1, maximum=MAX_PER_DROP)

    with write(db):
        entry = db.execute(
            """insert into pending_dropoffs (site_id, sample_count, dropped_by, note)
               values (%s, %s, %s, %s)
               returning id, sample_count, dropped_at""",
            (site['id'], count, text(data, 'dropped_by') or None, text(data, 'note') or None),
        ).fetchone()

        waiting = db.execute(
            """select coalesce(sum(sample_count), 0) as n
               from pending_dropoffs
               where site_id = %s and collected_at is null""",
            (site['id'],),
        ).fetchone()['n']

    # After the commit, so the email can never describe a drop that was rolled
    # back — and so a slow mail server cannot hold a write transaction open.
    _email_the_lab(db, site, count, text(data, 'dropped_by'), text(data, 'note'))

    return jsonify({
        'recorded': dict(entry),
        'site': site['name'],
        'total_waiting': waiting,
    }), 201


def _email_the_lab(db, site, count, dropped_by, note):
    """Best-effort notification. The drop is already saved either way."""
    from services import notify

    if not notify.configured():
        return
    try:
        sites = [dict(r) for r in db.execute(_SITE_SUMMARY).fetchall()]
        notify.notify_dropoff(
            site, count, sites,
            dropped_by=dropped_by or None,
            note=note or None,
            app_url=request.url_root.rstrip('/') + '/',
        )
    except Exception:
        # notify swallows its own errors; this guards the summary query, which
        # must not turn a recorded drop-off into a 500 for the person at the
        # freezer.
        current_app.logger.exception('Could not send the drop-off notification')
