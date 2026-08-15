"""API tests covering the behaviour that the SQLite-to-Postgres port could break."""

from datetime import date

import pytest


# ------------------------------------------------------------
# Authentication
# ------------------------------------------------------------

def test_api_requires_sign_in(anon):
    response = anon.get('/api/freezer')
    assert response.status_code == 401
    assert response.get_json()['error']


def test_pages_redirect_to_login(anon):
    response = anon.get('/')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_wrong_password_is_rejected(anon):
    response = anon.post('/login', data={'password': 'not-the-password'})
    assert response.status_code == 200
    assert b'not recognised' in response.data


def test_login_only_redirects_within_the_app(anon):
    response = anon.post(
        '/login?next=https://example.com/phish', data={'password': 'test-password'}
    )
    assert response.headers['Location'] == '/'


# ------------------------------------------------------------
# Freezer structure
# ------------------------------------------------------------

def test_freezer_tree_is_fully_nested(client):
    shelves = client.get('/api/freezer').get_json()

    assert len(shelves) == 3
    assert sum(len(s['racks']) for s in shelves) == 18
    assert sum(len(d['drawers']) for s in shelves for d in s['racks']) == 126

    boxes = [b for s in shelves for r in s['racks'] for d in r['drawers'] for b in d['boxes']]
    assert len(boxes) == 504
    assert all(b['capacity'] == 100 for b in boxes)
    assert all(b['occupied'] == 0 for b in boxes)

    upper = next(s for s in shelves if s['position'] == 1)
    assert upper['section'] == 'raptor'
    assert upper['racks'][0]['designation'] == 'RTHA / RSHA / SWHA'


def test_freezer_tree_uses_a_fixed_number_of_queries(client, flask_app):
    """The nested-loop version issued ~148 queries; this must stay flat."""
    import db as db_module

    real_get_db = db_module.get_db
    counter = {'n': 0}

    class CountingConnection:
        def __init__(self, inner):
            self._inner = inner

        def execute(self, *args, **kwargs):
            counter['n'] += 1
            return self._inner.execute(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._inner, name)

    from routes import freezer as freezer_routes

    freezer_routes.get_db = lambda: CountingConnection(real_get_db())
    try:
        client.get('/api/freezer')
    finally:
        freezer_routes.get_db = real_get_db

    assert counter['n'] == 4, f'expected 4 queries, got {counter["n"]}'


def test_box_detail_includes_location(client, boxes):
    box = client.get(f'/api/boxes/{boxes["raptor"]["id"]}').get_json()
    assert box['section'] == 'raptor'
    assert box['shelf_name'] == 'Upper Shelf'
    assert box['rack_label'].startswith('Rack U')
    assert box['tubes'] == []


def test_missing_box_returns_404(client):
    response = client.get('/api/boxes/999999')
    assert response.status_code == 404
    assert response.get_json()['error'] == 'Box not found.'


# ------------------------------------------------------------
# Research tubes
# ------------------------------------------------------------

def test_research_tube_round_trip(client, boxes):
    box_id = boxes['research']['id']
    created = client.post('/api/research/tubes', json={
        'box_id': box_id, 'row_pos': 2, 'col_pos': 3,
        'sample_id': 'EXP-2026-042', 'description': 'Plasma, spun',
        'date_stored': '2026-03-14',
    })
    assert created.status_code == 201
    tube = created.get_json()

    # Dates must come back as ISO strings the date inputs can read.
    assert tube['date_stored'] == '2026-03-14'
    assert tube['freeze_thaw_cycles'] == 0

    updated = client.put(f'/api/research/tubes/{tube["id"]}', json={
        'sample_id': 'EXP-2026-042', 'description': 'Plasma, spun, aliquot A',
        'date_stored': '2026-03-14', 'freeze_thaw_cycles': 1,
    }).get_json()
    assert updated['description'].endswith('aliquot A')
    assert updated['freeze_thaw_cycles'] == 1

    thawed = client.put(f'/api/research/tubes/{tube["id"]}/thaw').get_json()
    assert thawed['freeze_thaw_cycles'] == 2

    assert client.delete(f'/api/research/tubes/{tube["id"]}').status_code == 200
    assert client.delete(f'/api/research/tubes/{tube["id"]}').status_code == 404


def test_occupied_position_gets_a_readable_error(client, boxes):
    box_id = boxes['research']['id']
    payload = {'box_id': box_id, 'row_pos': 1, 'col_pos': 1, 'sample_id': 'FIRST'}
    assert client.post('/api/research/tubes', json=payload).status_code == 201

    clash = client.post('/api/research/tubes', json={**payload, 'sample_id': 'SECOND'})
    assert clash.status_code == 400
    error = clash.get_json()['error']
    assert error == 'That position already holds a tube.'
    # The raw constraint name must never reach the browser.
    assert 'row_pos' not in error


def test_bad_date_is_rejected_by_name(client, boxes):
    response = client.post('/api/research/tubes', json={
        'box_id': boxes['research']['id'], 'row_pos': 4, 'col_pos': 4,
        'date_stored': 'the fourteenth',
    })
    assert response.status_code == 400
    assert 'date_stored' in response.get_json()['error']


def test_research_search_is_case_insensitive(client, boxes):
    """SQLite's LIKE ignored case; Postgres LIKE does not, so this uses ILIKE."""
    client.post('/api/research/tubes', json={
        'box_id': boxes['research']['id'], 'row_pos': 5, 'col_pos': 5,
        'sample_id': 'EXP-2026-042', 'description': 'Kestrel plasma',
    })

    for query in ('exp-2026', 'EXP-2026', 'kestrel', 'KESTREL'):
        results = client.get(f'/api/research/search?q={query}').get_json()
        assert len(results) == 1, f'search for {query!r} found nothing'
        assert results[0]['sample_id'] == 'EXP-2026-042'


def test_search_wildcards_are_literal(client, boxes):
    client.post('/api/research/tubes', json={
        'box_id': boxes['research']['id'], 'row_pos': 6, 'col_pos': 6, 'sample_id': 'PLAIN',
    })
    # '%' would match everything if it were passed through as a wildcard.
    assert client.get('/api/research/search?q=%').get_json() == []


# ------------------------------------------------------------
# Raptor tubes
# ------------------------------------------------------------

def test_raptor_tube_id_format_and_sequence(client, boxes, species_id):
    box_id = boxes['raptor']['id']

    first = client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
    }).get_json()
    assert first['tube_id'] == 'RTHA26001'
    assert first['collection_date'] == '2026-04-01'

    second = client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 1, 'col_pos': 2,
        'species_id': species_id, 'collection_date': '2026-05-02',
    }).get_json()
    assert second['tube_id'] == 'RTHA26002'

    # A different year restarts the count.
    other_year = client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 1, 'col_pos': 3,
        'species_id': species_id, 'collection_date': '2027-01-05',
    }).get_json()
    assert other_year['tube_id'] == 'RTHA27001'


def test_multi_tube_sample_fills_free_positions(client, boxes, species_id):
    box_id = boxes['raptor']['id']

    # Block one slot so the allocator has to skip it.
    client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 1, 'col_pos': 2,
        'species_id': species_id, 'collection_date': '2026-04-01',
    })

    result = client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-02', 'num_tubes': 3,
    })
    assert result.status_code == 201
    tubes = result.get_json()['tubes']

    assert [t['tube_id'] for t in tubes] == ['RTHA26002-1', 'RTHA26002-2', 'RTHA26002-3']
    assert [(t['row_pos'], t['col_pos']) for t in tubes] == [(1, 1), (1, 3), (1, 4)]


def test_failed_insert_does_not_consume_a_tube_number(client, boxes, species_id):
    box_id = boxes['raptor']['id']
    client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
    })

    clash = client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-02',
    })
    assert clash.status_code == 400

    # The rolled-back attempt must not have burned RTHA26002.
    recovered = client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 2, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-03',
    }).get_json()
    assert recovered['tube_id'] == 'RTHA26002'


def test_sample_type_defaults_to_plasma(client, boxes, species_id):
    tube = client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
    }).get_json()
    assert tube['sample_type'] == 'Plasma'


def test_sample_type_round_trips(client, boxes, species_id):
    box_id = boxes['raptor']['id']
    tube = client.post('/api/raptor/tubes', json={
        'box_id': box_id, 'row_pos': 2, 'col_pos': 2,
        'species_id': species_id, 'collection_date': '2026-04-01',
        'sample_type': 'Liver',
    }).get_json()
    assert tube['sample_type'] == 'Liver'

    updated = client.put(f'/api/raptor/tubes/{tube["id"]}', json={
        'collection_date': '2026-04-01', 'sample_type': 'Other',
        'notes': 'Kidney, left',
    }).get_json()
    assert updated['sample_type'] == 'Other'
    assert updated['notes'] == 'Kidney, left'

    # The box view feeds the grid, so it has to carry the type as well.
    box = client.get(f'/api/boxes/{box_id}').get_json()
    assert box['tubes'][0]['sample_type'] == 'Other'


def test_multi_tube_sample_shares_its_type(client, boxes, species_id):
    result = client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
        'sample_type': 'Liver', 'num_tubes': 3,
    }).get_json()
    assert [t['sample_type'] for t in result['tubes']] == ['Liver'] * 3


def test_sample_type_reaches_the_export(client, boxes, species_id):
    client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
        'sample_type': 'Liver',
    })
    csv_bytes = client.get('/api/export/raptor/csv').data
    assert b'Sample Type' in csv_bytes
    assert b'Liver' in csv_bytes


def test_raptor_tube_rejects_a_research_box(client, boxes, species_id):
    response = client.post('/api/raptor/tubes', json={
        'box_id': boxes['research']['id'], 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
    })
    assert response.status_code == 400
    assert 'research section' in response.get_json()['error']


def test_raptor_search_and_lookup(client, boxes, species_id):
    client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 3, 'col_pos': 3,
        'species_id': species_id, 'collection_date': '2026-04-01',
        'wrmd_number': '12345',
    })

    for query in ('rtha', 'red-tailed', 'RED-TAILED', '12345'):
        assert len(client.get(f'/api/raptor/search?q={query}').get_json()) == 1

    found = client.get('/api/raptor/lookup/rtha26001').get_json()
    assert found['tube_id'] == 'RTHA26001'
    assert found['box_label'].startswith('U1')

    assert client.get('/api/raptor/lookup/NOPE99999').status_code == 404


def test_new_species_validation(client):
    assert client.post('/api/species', json={
        'common_name': 'Test Kite', 'scientific_name': 'Testus kitus', 'banding_code': 'ZZ',
    }).status_code == 400

    created = client.post('/api/species', json={
        'common_name': 'Test Kite', 'scientific_name': 'Testus kitus', 'banding_code': 'zzzz',
    })
    assert created.status_code == 201

    duplicate = client.post('/api/species', json={
        'common_name': 'Test Kite', 'scientific_name': 'Testus kitus', 'banding_code': 'ZZZZ',
    })
    assert duplicate.status_code == 400
    assert 'banding code' in duplicate.get_json()['error']


# ------------------------------------------------------------
# Box maintenance
# ------------------------------------------------------------

def test_shrinking_a_box_cannot_strand_tubes(client, boxes):
    box_id = boxes['research']['id']
    client.post('/api/research/tubes', json={
        'box_id': box_id, 'row_pos': 9, 'col_pos': 9, 'sample_id': 'DEEP',
    })

    blocked = client.put(f'/api/boxes/{box_id}',
                         json={'label': 'Shrunk', 'grid_rows': 5, 'grid_cols': 5})
    assert blocked.status_code == 400
    assert 'outside a 5x5 grid' in blocked.get_json()['error']

    allowed = client.put(f'/api/boxes/{box_id}',
                         json={'label': 'Still fine', 'grid_rows': 10, 'grid_cols': 10})
    assert allowed.status_code == 200


def test_box_with_tubes_cannot_be_deleted(client, boxes):
    box_id = boxes['research']['id']
    client.post('/api/research/tubes', json={
        'box_id': box_id, 'row_pos': 1, 'col_pos': 1, 'sample_id': 'HERE',
    })
    response = client.delete(f'/api/boxes/{box_id}')
    assert response.status_code == 400
    assert 'still holds 1 tube' in response.get_json()['error']


# ------------------------------------------------------------
# Statistics
# ------------------------------------------------------------

def test_stats_count_birds_not_tubes(client, boxes, species_id):
    client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
        'num_tubes': 4, 'age': 'Adult', 'sex': 'Female',
    })

    raptor = client.get('/api/stats/raptor').get_json()
    assert raptor['total_samples'] == 1, 'four tubes from one bird is one sample'
    assert raptor['total_tubes'] == 4
    assert raptor['species_breakdown'][0] == {'species': 'Red-tailed Hawk', 'code': 'RTHA', 'count': 1}
    assert raptor['monthly_counts'] == [{'month': '2026-04', 'count': 1}]
    assert raptor['age_distribution'] == [{'age': 'Adult', 'count': 1}]
    assert isinstance(raptor['avg_freeze_thaw_cycles'], float)

    freezer = client.get('/api/stats/freezer').get_json()
    assert freezer['total_boxes'] == 504
    assert freezer['total_capacity'] == 50400
    assert freezer['raptor_count'] == 1
    assert freezer['tubes_stored'] == 4, 'occupancy counts physical tubes'


def test_research_stats(client, boxes):
    client.post('/api/research/tubes', json={
        'box_id': boxes['research']['id'], 'row_pos': 1, 'col_pos': 1, 'sample_id': 'A',
    })
    stats = client.get('/api/stats/research').get_json()
    assert stats['total_samples'] == 1
    assert stats['boxes_with_samples'] == 1
    assert stats['total_boxes'] == 336


# ------------------------------------------------------------
# Exports
# ------------------------------------------------------------

@pytest.mark.parametrize('section,fmt,signature', [
    ('raptor', 'xlsx', b'PK'),
    ('raptor', 'csv', None),
    ('research', 'xlsx', b'PK'),
    ('research', 'csv', None),
])
def test_exports_download(client, boxes, species_id, section, fmt, signature):
    client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01', 'notes': 'test',
    })
    client.post('/api/research/tubes', json={
        'box_id': boxes['research']['id'], 'row_pos': 1, 'col_pos': 1, 'sample_id': 'A',
        'date_stored': '2026-04-01',
    })

    response = client.get(f'/api/export/{section}/{fmt}')
    assert response.status_code == 200
    assert date.today().isoformat() in response.headers['Content-Disposition']

    if signature:
        assert response.data.startswith(signature)
    else:
        # Excel needs the BOM to read UTF-8 CSV correctly.
        assert response.data.startswith(b'\xef\xbb\xbf')
        assert b'Position' in response.data
        assert b'A1' in response.data


def test_raptor_export_respects_filters(client, boxes, species_id):
    client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
    })

    inside = client.get('/api/export/raptor/csv?date_from=2026-01-01&date_to=2026-12-31')
    assert b'RTHA26001' in inside.data

    outside = client.get('/api/export/raptor/csv?date_from=2027-01-01')
    assert b'RTHA26001' not in outside.data


# ------------------------------------------------------------
# Health
# ------------------------------------------------------------

def test_health_is_public_and_checks_the_database(anon):
    response = anon.get('/api/health')
    assert response.status_code == 200
    body = response.get_json()
    assert body['status'] == 'ok'
    assert body['database'] == 'connected'
    assert body['schema'] == 'current'


def test_health_names_pending_migrations(anon, flask_app):
    """A missing migration should name itself, not surface as a 500 elsewhere."""
    from db import get_db

    with flask_app.app_context():
        db = get_db()
        db.execute("delete from schema_migrations where filename like '%add_sample_type%'")
        db.commit()
    try:
        response = anon.get('/api/health')
        assert response.status_code == 503
        body = response.get_json()
        assert body['schema'] == 'out of date'
        assert body['pending_migrations'] == ['20260815000002_add_sample_type.sql']
    finally:
        with flask_app.app_context():
            db = get_db()
            db.execute("insert into schema_migrations (filename) values "
                       "('20260815000002_add_sample_type.sql') on conflict do nothing")
            db.commit()


def test_migrations_are_applied_in_place_and_are_idempotent(client, flask_app):
    """The upgrade path a deployed database actually takes: forget everything
    that has been applied, replay it, and confirm nothing was lost."""
    from db import get_db

    with flask_app.app_context():
        db = get_db()
        db.execute('delete from schema_migrations')
        db.commit()
        before = db.execute('select count(*) as n from species').fetchone()['n']

    from services.migrator import available

    with flask_app.app_context():
        token_before = get_db().execute(
            "select token from collection_sites where code = 'CRC'").fetchone()['token']

    first = client.post('/api/admin/migrate').get_json()
    assert first['applied'] == available(), first
    assert first['applied'][0].startswith('20260815000000')

    # Replaying the seed must not duplicate reference data.
    with flask_app.app_context():
        db = get_db()
        assert db.execute('select count(*) as n from species').fetchone()['n'] == before
        assert db.execute('select count(*) as n from boxes').fetchone()['n'] == 504
        assert db.execute('select count(*) as n from collection_sites').fetchone()['n'] == 2

        # Replaying must not rotate the site tokens — printed QR codes on the
        # satellite freezers would stop working.
        assert db.execute(
            "select token from collection_sites where code = 'CRC'"
        ).fetchone()['token'] == token_before

    # And a second pass has nothing left to do.
    assert client.post('/api/admin/migrate').get_json() == {'applied': [], 'count': 0}
    assert client.get('/api/health').get_json()['schema'] == 'current'


def test_migrate_requires_a_session(anon):
    assert anon.post('/api/admin/migrate').status_code == 401


# ------------------------------------------------------------
# Retrieval log
# ------------------------------------------------------------

def test_retrieval_logs_and_counts_a_thaw(client, boxes, species_id):
    tube = client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 1, 'col_pos': 1,
        'species_id': species_id, 'collection_date': '2026-04-01',
    }).get_json()
    assert tube['freeze_thaw_cycles'] == 0

    entry = client.post('/api/retrievals', json={
        'section': 'raptor', 'tube_id': tube['id'],
        'retrieved_by': 'H. Beaufrere', 'purpose': 'PCV assay',
    })
    assert entry.status_code == 201
    logged = entry.get_json()
    assert logged['tube_label'] == 'RTHA26001'
    assert logged['species_name'] == 'Red-tailed Hawk'
    assert logged['position_label'] == 'A1'
    assert logged['consumed'] is False

    # Taking a tube out of a -80 freezer is a thaw.
    box = client.get(f'/api/boxes/{boxes["raptor"]["id"]}').get_json()
    assert box['tubes'][0]['freeze_thaw_cycles'] == 1


def test_retrieval_survives_the_tube_being_deleted(client, boxes, species_id):
    """Chain of custody has to outlive the specimen."""
    tube = client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 2, 'col_pos': 2,
        'species_id': species_id, 'collection_date': '2026-04-01',
    }).get_json()
    client.post('/api/retrievals', json={
        'section': 'raptor', 'tube_id': tube['id'],
        'retrieved_by': 'H. Beaufrere', 'consumed': True,
    })
    client.delete(f'/api/raptor/tubes/{tube["id"]}')

    entries = client.get('/api/retrievals').get_json()['entries']
    assert len(entries) == 1
    assert entries[0]['tube_label'] == 'RTHA26001'
    assert entries[0]['raptor_tube_id'] is None
    assert entries[0]['consumed'] is True


def test_retrieval_log_filters_and_paginates(client, boxes, species_id):
    raptor = client.post('/api/raptor/tubes', json={
        'box_id': boxes['raptor']['id'], 'row_pos': 3, 'col_pos': 3,
        'species_id': species_id, 'collection_date': '2026-04-01',
    }).get_json()
    research = client.post('/api/research/tubes', json={
        'box_id': boxes['research']['id'], 'row_pos': 1, 'col_pos': 1,
        'sample_id': 'EXP-1',
    }).get_json()

    client.post('/api/retrievals', json={
        'section': 'raptor', 'tube_id': raptor['id'],
        'retrieved_by': 'Alice', 'purpose': 'Chemistry panel'})
    client.post('/api/retrievals', json={
        'section': 'research', 'tube_id': research['id'],
        'retrieved_by': 'Bob', 'purpose': 'Shipment'})

    assert client.get('/api/retrievals').get_json()['total'] == 2
    assert client.get('/api/retrievals?section=raptor').get_json()['total'] == 1
    assert client.get('/api/retrievals?q=alice').get_json()['total'] == 1
    assert client.get('/api/retrievals?q=SHIPMENT').get_json()['total'] == 1

    page = client.get('/api/retrievals?limit=1').get_json()
    assert len(page['entries']) == 1 and page['total'] == 2

    stats = client.get('/api/stats/retrievals').get_json()
    assert stats['total'] == 2 and stats['people'] == 2


def test_retrieval_requires_a_real_tube(client):
    response = client.post('/api/retrievals', json={
        'section': 'raptor', 'tube_id': 999999, 'retrieved_by': 'Alice'})
    assert response.status_code == 404


# ------------------------------------------------------------
# Drawer notes
# ------------------------------------------------------------

def test_drawer_note_round_trips(client, flask_app):
    from db import get_db

    with flask_app.app_context():
        drawer_id = get_db().execute('select id from drawers order by id limit 1').fetchone()['id']

    saved = client.put(f'/api/drawers/{drawer_id}', json={'note': 'West Nile study 2026'})
    assert saved.status_code == 200
    assert saved.get_json()['note'] == 'West Nile study 2026'

    shelves = client.get('/api/freezer').get_json()
    notes = [d['note'] for s in shelves for r in s['racks'] for d in r['drawers']]
    assert 'West Nile study 2026' in notes

    cleared = client.put(f'/api/drawers/{drawer_id}', json={'note': ''})
    assert cleared.get_json()['note'] is None


def test_drawer_note_length_is_capped(client, flask_app):
    from db import get_db

    with flask_app.app_context():
        drawer_id = get_db().execute('select id from drawers order by id limit 1').fetchone()['id']

    response = client.put(f'/api/drawers/{drawer_id}', json={'note': 'x' * 201})
    assert response.status_code == 400
    assert '200 characters' in response.get_json()['error']


# ------------------------------------------------------------
# Satellite collection sites
# ------------------------------------------------------------

def _site(client, code):
    return next(s for s in client.get('/api/collection-sites').get_json()
                if s['code'] == code)


def _token(flask_app, code):
    from db import get_db

    with flask_app.app_context():
        return get_db().execute(
            'select token from collection_sites where code = %s', (code,)
        ).fetchone()['token']


def test_both_satellite_sites_exist_and_start_empty(client):
    sites = client.get('/api/collection-sites').get_json()
    assert [s['code'] for s in sites] == ['CRC', 'VMTH']
    assert all(s['pending_samples'] == 0 for s in sites)
    assert all(s['oldest_age_days'] is None for s in sites)
    # The token must never ride along on the list used by every page.
    assert all('token' not in s for s in sites)


def test_dropoff_needs_no_login(anon, flask_app):
    """People at the freezer have a phone and no lab password."""
    token = _token(flask_app, 'CRC')

    page = anon.get(f'/drop/{token}')
    assert page.status_code == 200
    assert b'How many samples' in page.data

    recorded = anon.post(f'/api/drop/{token}', json={'sample_count': 3,
                                                     'dropped_by': 'Volunteer'})
    assert recorded.status_code == 201
    assert recorded.get_json()['total_waiting'] == 3


def test_a_bad_token_gets_nowhere(anon):
    assert anon.get('/drop/' + 'f' * 32).status_code == 404
    assert anon.get('/drop/short').status_code == 404
    assert anon.post('/api/drop/' + 'f' * 32, json={'sample_count': 1}).status_code == 404


def test_dropoff_count_is_bounded(anon, flask_app):
    token = _token(flask_app, 'CRC')
    assert anon.post(f'/api/drop/{token}', json={'sample_count': 0}).status_code == 400
    assert anon.post(f'/api/drop/{token}', json={'sample_count': 501}).status_code == 400
    assert anon.post(f'/api/drop/{token}', json={'sample_count': 'lots'}).status_code == 400


def test_pending_counts_and_age_per_site(client, flask_app, anon):
    from db import get_db

    crc, vmth = _token(flask_app, 'CRC'), _token(flask_app, 'VMTH')
    anon.post(f'/api/drop/{crc}', json={'sample_count': 4})
    anon.post(f'/api/drop/{crc}', json={'sample_count': 2})
    anon.post(f'/api/drop/{vmth}', json={'sample_count': 7})

    # Age the oldest CRC drop so the days figure has something to report.
    with flask_app.app_context():
        db = get_db()
        db.execute("""update pending_dropoffs set dropped_at = now() - interval '9 days'
                      where id = (select min(id) from pending_dropoffs)""")
        db.commit()

    assert _site(client, 'CRC')['pending_samples'] == 6
    assert _site(client, 'CRC')['oldest_age_days'] == 9
    assert _site(client, 'VMTH')['pending_samples'] == 7
    assert _site(client, 'VMTH')['oldest_age_days'] == 0


def test_sites_are_collected_independently(client, flask_app, anon):
    crc, vmth = _token(flask_app, 'CRC'), _token(flask_app, 'VMTH')
    anon.post(f'/api/drop/{crc}', json={'sample_count': 5})
    anon.post(f'/api/drop/{vmth}', json={'sample_count': 8})

    result = client.post(f'/api/collection-sites/{_site(client, "CRC")["id"]}/collect',
                         json={'collected_by': 'H. Beaufrere'}).get_json()
    assert result == {'collected_dropoffs': 1, 'collected_samples': 5}

    # CRC resets; VMTH is untouched.
    assert _site(client, 'CRC')['pending_samples'] == 0
    assert _site(client, 'CRC')['oldest_age_days'] is None
    assert _site(client, 'VMTH')['pending_samples'] == 8

    # Collecting keeps the history rather than deleting it.
    history = client.get(
        f'/api/collection-sites/{_site(client, "CRC")["id"]}/dropoffs').get_json()
    assert len(history) == 1
    assert history[0]['collected_at'] is not None
    assert history[0]['collected_by'] == 'H. Beaufrere'

    # And a drop after collection starts a fresh backlog.
    anon.post(f'/api/drop/{crc}', json={'sample_count': 2})
    assert _site(client, 'CRC')['pending_samples'] == 2


def test_qr_endpoint_returns_the_drop_url(client, flask_app):
    site = _site(client, 'VMTH')
    info = client.get(f'/api/collection-sites/{site["id"]}/qr').get_json()
    assert info['code'] == 'VMTH'
    assert info['drop_url'].endswith('/drop/' + _token(flask_app, 'VMTH'))


def test_collection_admin_needs_a_session(anon, client):
    site_id = _site(client, 'CRC')['id']
    assert anon.get('/api/collection-sites').status_code == 401
    assert anon.post(f'/api/collection-sites/{site_id}/collect').status_code == 401
    assert anon.get(f'/api/collection-sites/{site_id}/qr').status_code == 401
