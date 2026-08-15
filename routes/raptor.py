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
    require(data, 'box_id', 'row_pos', 'col_pos', 'species_id', 'collection_date')

    box_id = as_int(data, 'box_id')
    row_pos = as_int(data, 'row_pos', minimum=1)
    col_pos = as_int(data, 'col_pos', minimum=1)
    species_id = as_int(data, 'species_id')
    collection_date = as_date(data, 'collection_date', required=True)
    num_tubes = as_int(data, 'num_tubes', minimum=1, maximum=MAX_TUBES_PER_SAMPLE, default=1)

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
        text(data, 'age'),
        text(data, 'sex'),
        as_int(data, 'freeze_thaw_cycles', minimum=0, default=0),
        text(data, 'wrmd_number'),
        text(data, 'vmth_number'),
        text(data, 'notes'),
    )

    with write(db):
        base_id = generate_raptor_tube_id(
            db, species['banding_code'], species['id'], collection_date
        )

        if num_tubes == 1:
            placements = [(base_id, row_pos, col_pos)]
        else:
            positions = _free_positions(
                db, box_id, box['grid_rows'], box['grid_cols'], row_pos, col_pos, num_tubes
            )
            if len(positions) < num_tubes:
                raise ApiError(
                    f'Only {len(positions)} free position(s) left in this box, '
                    f'but {num_tubes} tubes were requested.'
                )
            placements = [
                (f'{base_id}-{i + 1}', r, c) for i, (r, c) in enumerate(positions)
            ]

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
