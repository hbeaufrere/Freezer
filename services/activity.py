"""Recording what happened, so the log can say so later.

Every row is a snapshot: the tube's label, where it was, which species, in
words. Nothing here references a tube by id, because the point of a log is
to outlive what it describes.
"""

from flask import has_request_context, request

# Row letters skip I, matching the grid and the exports.
_ROW_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K']


def position_label(row_pos, col_pos):
    if row_pos is None or col_pos is None:
        return None
    letter = _ROW_LETTERS[row_pos - 1] if row_pos <= len(_ROW_LETTERS) else chr(64 + row_pos)
    return f'{letter}{col_pos}'


def actor():
    """Who is at the keyboard, as the browser says. The app has one shared
    password, so the name is self-declared — the same name the retrieval
    sheet remembers — and absent when nobody has given one."""
    if not has_request_context():
        return None
    who = (request.headers.get('X-Freezer-User') or '').strip()
    return who[:100] or None


def record(db, kind, section, *, tube_label=None, box_label=None, position_label=None,
           species_name=None, detail=None):
    """Insert one event. Call inside the write that it describes, so the two
    commit or roll back together."""
    db.execute(
        """insert into activity
               (section, kind, tube_label, box_label, position_label, species_name, detail, actor)
           values (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (section, kind, tube_label, box_label, position_label, species_name, detail, actor()),
    )


def raptor_snapshot(db, tube_id):
    row = db.execute(
        """select rt.tube_id as label, rt.row_pos, rt.col_pos, s.common_name, b.label as box_label
           from raptor_tubes rt join species s on rt.species_id = s.id
           join boxes b on rt.box_id = b.id where rt.id = %s""", (tube_id,)
    ).fetchone()
    return row and {'tube_label': row['label'], 'box_label': row['box_label'],
                    'position_label': position_label(row['row_pos'], row['col_pos']),
                    'species_name': row['common_name']}


def research_snapshot(db, tube_id):
    row = db.execute(
        """select rt.sample_id as label, rt.row_pos, rt.col_pos, b.label as box_label
           from research_tubes rt join boxes b on rt.box_id = b.id where rt.id = %s""", (tube_id,)
    ).fetchone()
    return row and {'tube_label': row['label'] or 'Untitled sample', 'box_label': row['box_label'],
                    'position_label': position_label(row['row_pos'], row['col_pos'])}


def snapshot(db, section, tube_id):
    return raptor_snapshot(db, tube_id) if section == 'raptor' else research_snapshot(db, tube_id)
