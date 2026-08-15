"""Retrieval log — who took which tube out, when, and what for.

Recording a retrieval also bumps that tube's freeze-thaw count, because taking
a tube out of a -80 freezer is a thaw whether or not anyone remembers to tick
the box separately.
"""

from flask import Blueprint, jsonify, request

from db import ApiError, get_db
from routes.support import as_int, json_body, like_pattern, one_or_404, require, text, write

retrieval_bp = Blueprint('retrieval', __name__)

PAGE_SIZE = 50

_COLUMNS = """
    id, section, raptor_tube_id, research_tube_id, tube_label, box_label,
    position_label, species_name, retrieved_at, retrieved_by, purpose,
    notes, consumed
"""

# Row letters skip I, matching the grid and the exports.
_ROW_LABELS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K']


def _position_label(row_pos, col_pos):
    if row_pos is None or col_pos is None:
        return None
    letter = _ROW_LABELS[row_pos - 1] if row_pos <= len(_ROW_LABELS) else chr(64 + row_pos)
    return f'{letter}{col_pos}'


@retrieval_bp.route('/api/retrievals')
def list_retrievals():
    """Most recent first, optionally filtered by free text or section."""
    db = get_db()
    limit = min(request.args.get('limit', PAGE_SIZE, type=int) or PAGE_SIZE, 200)
    offset = max(request.args.get('offset', 0, type=int) or 0, 0)
    section = request.args.get('section') or None
    query = (request.args.get('q') or '').strip()

    where, params = [], {'limit': limit, 'offset': offset}
    if section in ('raptor', 'research'):
        where.append('section = %(section)s')
        params['section'] = section
    if query:
        where.append("""(tube_label ilike %(q)s or retrieved_by ilike %(q)s
                         or purpose ilike %(q)s or notes ilike %(q)s
                         or species_name ilike %(q)s)""")
        params['q'] = like_pattern(query)

    clause = (' where ' + ' and '.join(where)) if where else ''

    rows = db.execute(
        f"""select {_COLUMNS} from retrievals {clause}
            order by retrieved_at desc, id desc
            limit %(limit)s offset %(offset)s""",
        params,
    ).fetchall()

    total = db.execute(
        f'select count(*) as n from retrievals {clause}', params
    ).fetchone()['n']

    return jsonify({'entries': [dict(r) for r in rows], 'total': total,
                    'limit': limit, 'offset': offset})


@retrieval_bp.route('/api/retrievals', methods=['POST'])
def create_retrieval():
    """Log a retrieval against a tube, and count the thaw it implies."""
    db = get_db()
    data = json_body()
    require(data, 'section', 'tube_id', 'retrieved_by')

    section = text(data, 'section')
    if section not in ('raptor', 'research'):
        raise ApiError("Section must be either 'raptor' or 'research'.")

    tube_id = as_int(data, 'tube_id')
    consumed = bool(data.get('consumed'))

    if section == 'raptor':
        tube = one_or_404(db.execute(
            """select rt.id, rt.tube_id as label, rt.row_pos, rt.col_pos,
                      s.common_name, b.label as box_label
               from raptor_tubes rt
               join species s on rt.species_id = s.id
               join boxes b on rt.box_id = b.id
               where rt.id = %s""",
            (tube_id,),
        ).fetchone(), 'Tube')
        keys = {'raptor_tube_id': tube_id, 'research_tube_id': None}
        species_name = tube['common_name']
    else:
        tube = one_or_404(db.execute(
            """select rt.id, rt.sample_id as label, rt.row_pos, rt.col_pos,
                      b.label as box_label
               from research_tubes rt
               join boxes b on rt.box_id = b.id
               where rt.id = %s""",
            (tube_id,),
        ).fetchone(), 'Tube')
        keys = {'raptor_tube_id': None, 'research_tube_id': tube_id}
        species_name = None

    with write(db):
        entry = db.execute(
            f"""insert into retrievals
                    (section, raptor_tube_id, research_tube_id, tube_label,
                     box_label, position_label, species_name,
                     retrieved_by, purpose, notes, consumed)
                values (%(section)s, %(raptor_tube_id)s, %(research_tube_id)s,
                        %(tube_label)s, %(box_label)s, %(position_label)s,
                        %(species_name)s, %(retrieved_by)s, %(purpose)s,
                        %(notes)s, %(consumed)s)
                returning {_COLUMNS}""",
            {
                'section': section,
                **keys,
                'tube_label': tube['label'] or 'Untitled sample',
                'box_label': tube['box_label'],
                'position_label': _position_label(tube['row_pos'], tube['col_pos']),
                'species_name': species_name,
                'retrieved_by': text(data, 'retrieved_by'),
                'purpose': text(data, 'purpose'),
                'notes': text(data, 'notes'),
                'consumed': consumed,
            },
        ).fetchone()

        # Out of the freezer and back again is a freeze-thaw cycle.
        table = 'raptor_tubes' if section == 'raptor' else 'research_tubes'
        db.execute(
            f'update {table} set freeze_thaw_cycles = freeze_thaw_cycles + 1 where id = %s',
            (tube_id,),
        )

    return jsonify(dict(entry)), 201


@retrieval_bp.route('/api/retrievals/<int:entry_id>', methods=['DELETE'])
def delete_retrieval(entry_id):
    """Remove a mistaken entry. The freeze-thaw count is left alone — the tube
    did come out of the freezer, whatever the paperwork said afterwards."""
    db = get_db()
    with write(db):
        deleted = db.execute('delete from retrievals where id = %s', (entry_id,)).rowcount
    if not deleted:
        raise ApiError('Log entry not found.', 404)
    return jsonify({'success': True})


@retrieval_bp.route('/api/stats/retrievals')
def retrieval_stats():
    db = get_db()

    totals = db.execute(
        """select count(*) as total,
                  count(*) filter (where retrieved_at >= now() - interval '30 days') as last_30_days,
                  count(*) filter (where consumed) as consumed,
                  count(distinct retrieved_by) as people
           from retrievals"""
    ).fetchone()

    recent = db.execute(
        """select retrieved_by, count(*) as count
           from retrievals
           where retrieved_at >= now() - interval '365 days'
           group by retrieved_by
           order by count desc, retrieved_by
           limit 10"""
    ).fetchall()

    monthly = db.execute(
        """select to_char(retrieved_at, 'YYYY-MM') as month, count(*) as count
           from retrievals
           where retrieved_at >= now() - interval '365 days'
           group by month
           order by month"""
    ).fetchall()

    return jsonify({
        **dict(totals),
        'by_person': [dict(r) for r in recent],
        'monthly_counts': [dict(r) for r in monthly],
    })
