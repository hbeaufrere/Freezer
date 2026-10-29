"""Whole-freezer events: one short dated note, stamped on every sample that
was inside at the time.

The stamp is a link, not a copy, so the note can be corrected in one place;
and it is a link to the tube, not the slot, so it follows a tube that is
moved and dies with a tube that is used up. Samples filed after the event
never get the link. Whole-box entries are linked through their box slot,
since they have no tube rows of their own.
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify

from db import ApiError, get_db
from routes.support import as_int, json_body, require, text, write
from services.activity import actor, record

events_bp = Blueprint('events', __name__)

MAX_NOTE = 120

# What an event currently covers, counted live: tubes that have been used up
# since drop out, which is what "samples still affected" should mean.
_LIST = """
    select e.id, e.occurred_at, e.note, e.recorded_by, e.created_at,
           (select count(*) from raptor_tube_events t where t.event_id = e.id) as raptor_tubes,
           (select count(*) from research_tube_events t where t.event_id = e.id) as research_tubes,
           (select count(*) from box_events t where t.event_id = e.id) as whole_boxes
    from freezer_events e
"""


def _parse_when(data):
    raw = (data.get('occurred_at') or '').strip()
    if not raw:
        return datetime.now(timezone.utc)
    try:
        when = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        raise ApiError('occurred_at must be an ISO date-time, e.g. 2026-10-12T03:40.') from None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when > datetime.now(timezone.utc):
        raise ApiError('A freezer event cannot be in the future.')
    return when


@events_bp.route('/api/freezer-events')
def list_events():
    rows = get_db().execute(f'{_LIST} order by e.occurred_at desc, e.id desc').fetchall()
    return jsonify([dict(r) for r in rows])


@events_bp.route('/api/freezer-events/preview')
def preview_event():
    """How many samples an event recorded now would be stamped on."""
    db = get_db()
    row = db.execute(
        """select (select count(*) from raptor_tubes) as raptor_tubes,
                  (select count(*) from research_tubes) as research_tubes,
                  (select count(*) from boxes where box_type = 'bulk'
                      and (bulk_sample_type is not null or bulk_tube_count > 0 or bulk_study is not null))
                      as whole_boxes"""
    ).fetchone()
    return jsonify(dict(row))


@events_bp.route('/api/freezer-events', methods=['POST'])
def create_event():
    db = get_db()
    data = json_body()
    require(data, 'note')
    note = ' '.join(text(data, 'note').split())
    if not note:
        raise ApiError('Say what happened, in a few words.')
    if len(note) > MAX_NOTE:
        raise ApiError(f'Keep the note under {MAX_NOTE} characters; it goes on every sample.')
    when = _parse_when(data)

    with write(db):
        event = db.execute(
            """insert into freezer_events (occurred_at, note, recorded_by)
               values (%s, %s, %s) returning id""",
            (when, note, actor()),
        ).fetchone()
        eid = event['id']
        raptor = db.execute(
            'insert into raptor_tube_events (tube_id, event_id) select id, %s from raptor_tubes', (eid,)
        ).rowcount
        research = db.execute(
            'insert into research_tube_events (tube_id, event_id) select id, %s from research_tubes', (eid,)
        ).rowcount
        boxes = db.execute(
            """insert into box_events (box_id, event_id)
               select id, %s from boxes where box_type = 'bulk'
                 and (bulk_sample_type is not null or bulk_tube_count > 0 or bulk_study is not null)""",
            (eid,),
        ).rowcount
        record(db, 'event', 'freezer', detail=f'{note} · noted on {raptor} raptor tubes, '
                                              f'{research} research tubes, {boxes} whole boxes')
        row = db.execute(f'{_LIST} where e.id = %s', (eid,)).fetchone()

    return jsonify(dict(row)), 201


@events_bp.route('/api/freezer-events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    """Correct the note or the time. The links are left alone."""
    db = get_db()
    data = json_body()
    note = ' '.join(text(data, 'note').split())
    if not note or len(note) > MAX_NOTE:
        raise ApiError(f'The note must be 1 to {MAX_NOTE} characters.')
    when = _parse_when(data)
    with write(db):
        updated = db.execute(
            'update freezer_events set note = %s, occurred_at = %s where id = %s returning id',
            (note, when, event_id),
        ).fetchone()
        if not updated:
            raise ApiError('Event not found.', 404)
        row = db.execute(f'{_LIST} where e.id = %s', (event_id,)).fetchone()
    return jsonify(dict(row))


@events_bp.route('/api/freezer-events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    db = get_db()
    with write(db):
        row = db.execute(f'{_LIST} where e.id = %s', (event_id,)).fetchone()
        if not row:
            raise ApiError('Event not found.', 404)
        db.execute('delete from freezer_events where id = %s', (event_id,))
        record(db, 'event', 'freezer', detail=f'event removed: {row["note"]}')
    return jsonify({'success': True})
