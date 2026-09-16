"""Raptor biobank tube CRUD endpoints with auto-generated tube IDs."""

from flask import Blueprint, jsonify, request

from db import ApiError, get_db
from routes.support import (
    as_date,
    as_int,
    json_body,
    like_pattern,
    one_or_404,
    require,
    text,
    write,
)
from services.id_generator import generate_raptor_tube_id

raptor_bp = Blueprint('raptor', __name__)

MAX_TUBES_PER_SAMPLE = 20

_TUBE_SELECT = """
    select rt.id, rt.tube_id, rt.box_id, rt.row_pos, rt.col_pos, rt.species_id,
           s.banding_code, s.common_name, s.scientific_name,
           rt.sample_type, rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
           rt.wrmd_number, rt.vmth_number, rt.notes, rt.created_at, rt.updated_at
    from raptor_tubes rt
    join species s on rt.species_id = s.id
"""


def _fetch_tube(db, row_id):
    return db.execute(f'{_TUBE_SELECT} where rt.id = %s', (row_id,)).fetchone()


def _free_positions(db, box_id, grid_rows, grid_cols, start_row, start_col, count):
    """Empty slots in reading order, starting at the clicked cell and wrapping."""
    occupied = {
        (r['row_pos'], r['col_pos'])
        for r in db.execute(
            'select row_pos, col_pos from raptor_tubes where box_id = %s', (box_id,)
        ).fetchall()
    }

    ordered = [(r, c) for r in range(1, grid_rows + 1) for c in range(1, grid_cols + 1)]
    try:
        start = ordered.index((start_row, start_col))
    except ValueError:
        raise ApiError('That position is outside the box grid.') from None

    from_click = ordered[start:] + ordered[:start]
    return [pos for pos in from_click if pos not in occupied][:count]


# ------------------------------------------------------------
# One bird, several tubes
#
# A bird's samples share a base ID and differ by suffix: RTHA26001 is a bird
# with one tube; RTHA26001-1 / -2 / -3 are three tubes from it. The base is
# the bird, the suffix is the tube. Everything below works in those terms so a
# bird sampled three ways ends up as one bird with three tubes, not three
# birds — which is what happened when each sample type was filed separately
# and each filing drew a fresh sequence number.
# ------------------------------------------------------------

def bird_base(tube_id):
    """RTHA26001-2 -> RTHA26001. Tolerates whatever a person types."""
    return (tube_id or '').strip().upper().split('-')[0]


def _bird_tubes(db, base):
    """Every tube of one bird, whichever box each sits in."""
    return db.execute(
        f"""{_TUBE_SELECT}
            where rt.tube_id = %(base)s or rt.tube_id like %(pattern)s
            order by rt.tube_id""",
        {'base': base, 'pattern': base + '-%'},
    ).fetchall()


def _suffix_of(tube_id, base):
    """The tube number within its bird. A plain ID counts as tube 1."""
    rest = tube_id[len(base):]
    if not rest:
        return 1
    try:
        return int(rest.lstrip('-'))
    except ValueError:
        return 1


def _next_tube_ids(base, existing, count):
    """IDs for ``count`` more tubes of a bird that already has ``existing``.

    Never renumbers what is already there — those IDs are printed on frozen
    tubes — so the new ones simply continue from the highest in use.
    """
    highest = max((_suffix_of(t['tube_id'], base) for t in existing), default=0)
    return [f'{base}-{highest + i + 1}' for i in range(count)]


def _bird_from(tubes):
    """Bird-level facts, read off the tubes it already has. First tube wins;
    they are meant to agree, and where they do not, the earliest filed is the
    one somebody checked against the bird."""
    first = tubes[0]
    return {
        'bird_id': bird_base(first['tube_id']),
        'species_id': first['species_id'],
        'banding_code': first['banding_code'],
        'common_name': first['common_name'],
        'scientific_name': first['scientific_name'],
        'collection_date': first['collection_date'],
        'age': first['age'],
        'sex': first['sex'],
        'wrmd_number': first['wrmd_number'],
        'vmth_number': first['vmth_number'],
    }


@raptor_bp.route('/api/raptor/birds/<bird_id>')
def get_bird(bird_id):
    """A bird and every tube it has, wherever each one sits.

    Accepts a tube ID as well as a bird ID, since the one on the label in your
    hand is usually a tube.
    """
    db = get_db()
    base = bird_base(bird_id)
    tubes = _bird_tubes(db, base)
    if not tubes:
        raise ApiError(f'No bird with ID {base}.', 404)

    located = db.execute(
        """select rt.tube_id, rt.sample_type, rt.row_pos, rt.col_pos,
                  b.label as box_label, d.label as drawer_label, r.label as rack_label
           from raptor_tubes rt
           join boxes b on rt.box_id = b.id
           join drawers d on b.drawer_id = d.id
           join racks r on d.rack_id = r.id
           where rt.tube_id = %(base)s or rt.tube_id like %(pattern)s
           order by rt.tube_id""",
        {'base': base, 'pattern': base + '-%'},
    ).fetchall()

    return jsonify({
        **_bird_from(tubes),
        'tubes': [dict(r) for r in located],
        'next_tube_id': _next_tube_ids(base, tubes, 1)[0],
    })


@raptor_bp.route('/api/raptor/tubes')
def list_tubes():
    box_id = request.args.get('box_id', type=int)
    if not box_id:
        raise ApiError('box_id parameter required.')

    rows = get_db().execute(
        f'{_TUBE_SELECT} where rt.box_id = %s order by rt.row_pos, rt.col_pos',
        (box_id,),
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/raptor/tubes', methods=['POST'])
def create_tube():
    """Store one bird's sample, optionally split across several tubes.

    A single tube keeps the plain ID (RTHA26001); several tubes from the same
    bird share that base and gain a suffix (RTHA26001-1, RTHA26001-2, ...).
    """
    db = get_db()
    data = json_body()
    require(data, 'box_id', 'row_pos', 'col_pos')

    box_id = as_int(data, 'box_id')
    row_pos = as_int(data, 'row_pos', minimum=1)
    col_pos = as_int(data, 'col_pos', minimum=1)
    num_tubes = as_int(data, 'num_tubes', minimum=1, maximum=MAX_TUBES_PER_SAMPLE, default=1)

    # Two ways in. A new bird names its species and date and draws a fresh
    # sequence number. An existing bird is named by ID, and everything that
    # describes the bird — species, date, age, sex, case numbers — comes from
    # what is already on file, so one bird cannot drift into two.
    bird = None
    existing = []
    bird_id = bird_base(text(data, 'bird_id'))
    if bird_id:
        existing = _bird_tubes(db, bird_id)
        if not existing:
            raise ApiError(f'No bird with ID {bird_id}. Check the ID, or add it as a new bird.', 404)
        bird = _bird_from(existing)
        species_id = bird['species_id']
        collection_date = bird['collection_date']
    else:
        require(data, 'species_id', 'collection_date')
        species_id = as_int(data, 'species_id')
        collection_date = as_date(data, 'collection_date', required=True)

    species = one_or_404(
        db.execute('select id, banding_code from species where id = %s', (species_id,)).fetchone(),
        'Species',
    )
    box = one_or_404(
        db.execute(
            'select id, grid_rows, grid_cols, section from boxes where id = %s', (box_id,)
        ).fetchone(),
        'Box',
    )
    if box['section'] != 'raptor':
        raise ApiError('That box belongs to the research section.')

    shared = (
        text(data, 'sample_type', 'Plasma') or 'Plasma',
        bird['age'] if bird else text(data, 'age'),
        bird['sex'] if bird else text(data, 'sex'),
        as_int(data, 'freeze_thaw_cycles', minimum=0, default=0),
        bird['wrmd_number'] if bird else text(data, 'wrmd_number'),
        bird['vmth_number'] if bird else text(data, 'vmth_number'),
        text(data, 'notes'),
    )

    with write(db):
        if num_tubes == 1:
            positions = [(row_pos, col_pos)]
        else:
            positions = _free_positions(
                db, box_id, box['grid_rows'], box['grid_cols'], row_pos, col_pos, num_tubes
            )
            if len(positions) < num_tubes:
                raise ApiError(
                    f'Only {len(positions)} free position(s) left in this box, '
                    f'but {num_tubes} tubes were requested.'
                )

        if bird:
            # No new sequence number: the bird already has one.
            ids = _next_tube_ids(bird_id, existing, num_tubes)
        else:
            base_id = generate_raptor_tube_id(
                db, species['banding_code'], species['id'], collection_date
            )
            ids = [base_id] if num_tubes == 1 else [
                f'{base_id}-{i + 1}' for i in range(num_tubes)
            ]

        placements = [(tid, r, c) for tid, (r, c) in zip(ids, positions)]

        created = []
        for tube_id, r, c in placements:
            new_id = db.execute(
                """insert into raptor_tubes
                       (tube_id, box_id, row_pos, col_pos, species_id, collection_date,
                        sample_type, age, sex, freeze_thaw_cycles,
                        wrmd_number, vmth_number, notes)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   returning id""",
                (tube_id, box_id, r, c, species_id, collection_date, *shared),
            ).fetchone()['id']
            created.append(new_id)

        tubes = [dict(_fetch_tube(db, row_id)) for row_id in created]

    if num_tubes == 1:
        return jsonify(tubes[0]), 201
    return jsonify({'tubes': tubes}), 201


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>', methods=['PUT'])
def update_tube(tube_id):
    db = get_db()
    data = json_body()

    with write(db):
        updated = db.execute(
            """update raptor_tubes
               set collection_date = %s, sample_type = %s, age = %s, sex = %s,
                   freeze_thaw_cycles = %s, wrmd_number = %s, vmth_number = %s, notes = %s
               where id = %s
               returning id""",
            (
                as_date(data, 'collection_date', required=True),
                text(data, 'sample_type', 'Plasma') or 'Plasma',
                text(data, 'age'),
                text(data, 'sex'),
                as_int(data, 'freeze_thaw_cycles', minimum=0, default=0),
                text(data, 'wrmd_number'),
                text(data, 'vmth_number'),
                text(data, 'notes'),
                tube_id,
            ),
        ).fetchone()
        one_or_404(updated, 'Tube')
        tube = _fetch_tube(db, tube_id)

    return jsonify(dict(tube))


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>/thaw', methods=['PUT'])
def record_thaw(tube_id):
    """Record one more freeze-thaw cycle for this tube."""
    db = get_db()

    with write(db):
        updated = db.execute(
            """update raptor_tubes set freeze_thaw_cycles = freeze_thaw_cycles + 1
               where id = %s returning id""",
            (tube_id,),
        ).fetchone()
        one_or_404(updated, 'Tube')
        tube = _fetch_tube(db, tube_id)

    return jsonify(dict(tube))


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>/bird', methods=['PUT'])
def reassign_tube(tube_id):
    """Say that a tube already on file belongs to another bird.

    For the case where the same bird was filed twice — plasma under one ID,
    RBCs under the next — because the form had no way to say "same bird". The
    tube keeps its box, position, sample type and freeze-thaw count; it takes
    the bird's ID with the next free suffix, and the bird's species, date,
    age, sex and case numbers, since those describe the animal, not the tube.

    The old ID goes into the notes and stays searchable. It is printed on a
    tube in a freezer, and the person who next reads that label needs to be
    able to find out what it became.
    """
    db = get_db()
    data = json_body()
    require(data, 'bird_id')

    tube = one_or_404(_fetch_tube(db, tube_id), 'Tube')
    target = bird_base(text(data, 'bird_id'))

    if bird_base(tube['tube_id']) == target:
        raise ApiError(f'{tube["tube_id"]} already belongs to {target}.')

    existing = _bird_tubes(db, target)
    if not existing:
        raise ApiError(f'No bird with ID {target}.', 404)
    bird = _bird_from(existing)

    if bird['species_id'] != tube['species_id']:
        raise ApiError(
            f'{tube["tube_id"]} is a {tube["common_name"]} and {target} is a '
            f'{bird["common_name"]}. A tube cannot move to a bird of another species.'
        )

    old_id = tube['tube_id']
    new_id = _next_tube_ids(target, existing, 1)[0]
    note = f'Relabelled from {old_id}'
    notes = f'{tube["notes"]}\n{note}' if tube['notes'] else note

    with write(db):
        db.execute(
            """update raptor_tubes
               set tube_id = %s, collection_date = %s, age = %s, sex = %s,
                   wrmd_number = %s, vmth_number = %s, notes = %s
               where id = %s""",
            (new_id, bird['collection_date'], bird['age'], bird['sex'],
             bird['wrmd_number'], bird['vmth_number'], notes, tube_id),
        )
        # Log entries still tied to this tube follow the rename; the ones
        # whose tube is gone keep their snapshot, as they should.
        db.execute(
            'update retrievals set tube_label = %s where raptor_tube_id = %s',
            (new_id, tube_id),
        )
        updated = dict(_fetch_tube(db, tube_id))

    return jsonify({**updated, 'previous_tube_id': old_id})


@raptor_bp.route('/api/raptor/tubes/<int:tube_id>', methods=['DELETE'])
def delete_tube(tube_id):
    db = get_db()
    with write(db):
        deleted = db.execute('delete from raptor_tubes where id = %s', (tube_id,)).rowcount
    if not deleted:
        raise ApiError('Tube not found.', 404)
    return jsonify({'success': True})


@raptor_bp.route('/api/raptor/search')
def search_tubes():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    rows = get_db().execute(
        """select rt.id, rt.tube_id, rt.box_id, rt.row_pos, rt.col_pos,
                  s.banding_code, s.common_name, s.scientific_name,
                  rt.collection_date, rt.age, rt.sex, rt.freeze_thaw_cycles,
                  rt.wrmd_number, rt.vmth_number,
                  b.label as box_label, d.label as drawer_label,
                  r.label as rack_label, sh.name as shelf_name
           from raptor_tubes rt
           join species s on rt.species_id = s.id
           join boxes b on rt.box_id = b.id
           join drawers d on b.drawer_id = d.id
           join racks r on d.rack_id = r.id
           join shelves sh on r.shelf_id = sh.id
           where rt.tube_id ilike %(q)s
              or s.common_name ilike %(q)s
              or s.scientific_name ilike %(q)s
              or s.banding_code ilike %(q)s
              or rt.wrmd_number ilike %(q)s
              or rt.vmth_number ilike %(q)s
              or rt.notes ilike %(q)s
           order by rt.tube_id
           limit 50""",
        {'q': like_pattern(q)},
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/raptor/lookup/<tube_id_str>')
def lookup_by_tube_id(tube_id_str):
    """Find a tube by its printed ID, e.g. RTHA26001, with its location."""
    tube = get_db().execute(
        """select rt.id, rt.tube_id, rt.box_id, rt.row_pos, rt.col_pos, rt.species_id,
                  s.banding_code, s.common_name, s.scientific_name,
                  rt.sample_type, rt.collection_date, rt.age, rt.sex,
                  rt.freeze_thaw_cycles, rt.wrmd_number, rt.vmth_number, rt.notes,
                  b.label as box_label, d.label as drawer_label,
                  r.label as rack_label, sh.name as shelf_name
           from raptor_tubes rt
           join species s on rt.species_id = s.id
           join boxes b on rt.box_id = b.id
           join drawers d on b.drawer_id = d.id
           join racks r on d.rack_id = r.id
           join shelves sh on r.shelf_id = sh.id
           where rt.tube_id = %s""",
        (tube_id_str.upper(),),
    ).fetchone()
    return jsonify(dict(one_or_404(tube, 'Tube')))


@raptor_bp.route('/api/species')
def list_species():
    rows = get_db().execute(
        'select id, common_name, scientific_name, banding_code from species order by common_name'
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@raptor_bp.route('/api/species', methods=['POST'])
def create_species():
    db = get_db()
    data = json_body()
    require(data, 'common_name', 'scientific_name', 'banding_code')

    code = text(data, 'banding_code').upper()
    if len(code) != 4 or not code.isalpha():
        raise ApiError('Banding codes must be exactly four letters, A-Z.')

    with write(db):
        species_id = db.execute(
            """insert into species (common_name, scientific_name, banding_code)
               values (%s, %s, %s) returning id""",
            (text(data, 'common_name'), text(data, 'scientific_name'), code),
        ).fetchone()['id']

    return jsonify({'id': species_id}), 201


# ------------------------------------------------------------
# Biobank filter — how many samples match, and where they are
# ------------------------------------------------------------

# Enough to answer "have we got this, and where is it" on screen. The full
# record, notes included, is what the CSV is for.
FILTER_PAGE_SIZE = 250


@raptor_bp.route('/api/raptor/filter-options')
def filter_options():
    """The criteria worth offering, taken from what the biobank actually holds.

    Derived rather than hard-coded: a dropdown that lists a sample type nobody
    has ever collected wastes a click on an empty result, and one built from
    today's form would silently hide anything recorded before an option was
    added or after it was renamed.
    """
    db = get_db()

    def distinct(column):
        rows = db.execute(
            f"""select {column} as value, count(*) as count
                from raptor_tubes
                where {column} is not null and {column} <> ''
                group by {column}
                order by count desc, {column}"""
        ).fetchall()
        return [dict(r) for r in rows]

    species = db.execute(
        """select s.id, s.common_name, s.banding_code, count(rt.id) as count
           from species s
           join raptor_tubes rt on rt.species_id = s.id
           group by s.id, s.common_name, s.banding_code
           order by s.common_name"""
    ).fetchall()

    return jsonify({
        'species': [dict(r) for r in species],
        'sample_types': distinct('sample_type'),
        'sexes': distinct('sex'),
        'ages': distinct('age'),
        'total': db.execute('select count(*) as n from raptor_tubes').fetchone()['n'],
    })


@raptor_bp.route('/api/raptor/filter')
def filter_samples():
    """Samples matching the chosen criteria, with where each one is.

    ``matched`` is the whole result, not the page: the number on screen has to
    be the number the CSV will contain, or the count is worse than useless.
    """
    from services.export_service import format_position, raptor_query

    db = get_db()
    filters = {
        'species_id': request.args.get('species_id', type=int),
        'sample_type': (request.args.get('sample_type') or '').strip(),
        'sex': (request.args.get('sex') or '').strip(),
        'age': (request.args.get('age') or '').strip(),
        'date_from': as_date(request.args, 'date_from'),
        'date_to': as_date(request.args, 'date_to'),
    }

    query, params = raptor_query(filters)
    rows = db.execute(query, params).fetchall()

    samples = [{
        'tube_id': row['tube_id'],
        'banding_code': row['banding_code'],
        'common_name': row['common_name'],
        'sample_type': row['sample_type'],
        'collection_date': row['collection_date'],
        'age': row['age'],
        'sex': row['sex'],
        'freeze_thaw_cycles': row['freeze_thaw_cycles'],
        'wrmd_number': row['wrmd_number'],
        'vmth_number': row['vmth_number'],
        'shelf': row['shelf'],
        'rack': row['rack'],
        'drawer': row['drawer'],
        'box': row['box'],
        'position': format_position(row['row_pos'], row['col_pos']),
    } for row in rows[:FILTER_PAGE_SIZE]]

    return jsonify({
        'matched': len(rows),
        'birds': len({(r['tube_id'] or '').split('-')[0] for r in rows}),
        'showing': len(samples),
        'samples': samples,
    })
