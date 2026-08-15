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
    assert response.get_json() == {'status': 'ok', 'database': 'connected'}
