"""Test fixtures.

These run against a real PostgreSQL database, because almost everything worth
testing here is SQL. Point DATABASE_URL at a scratch database with the
migrations applied; without it the suite skips rather than failing.

    createdb freezer_test
    DATABASE_URL=postgresql://localhost/freezer_test pytest

The suite applies the migrations itself, so an empty database is enough.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_PASSWORD = 'test-password'

os.environ.setdefault('SECRET_KEY', 'test-secret-key-not-for-production')
os.environ.setdefault('FREEZER_PASSWORD', TEST_PASSWORD)
os.environ.setdefault('FLASK_ENV', 'development')


@pytest.fixture(scope='session')
def flask_app():
    if not os.environ.get('DATABASE_URL'):
        pytest.skip('DATABASE_URL is not set; skipping database-backed tests')

    from app import create_app

    application = create_app()
    application.config.update(TESTING=True)

    # Bring the scratch database up to date the same way the app does, so the
    # suite exercises the real migration path rather than a psql-loaded schema.
    from db import get_db
    from services.migrator import apply_pending

    with application.app_context():
        apply_pending(get_db())

    return application


@pytest.fixture(autouse=True)
def clean_database(flask_app):
    """Every test starts with an empty freezer but the full structure intact."""
    from db import get_db

    with flask_app.app_context():
        db = get_db()
        db.execute('truncate retrievals, raptor_tubes, research_tubes, raptor_id_sequence restart identity')
        db.execute('truncate pending_dropoffs restart identity')
        db.execute('update drawers set note = null')
        # Research racks are seeded with no designation; tests that name one
        # must not leave the name for the next test to find.
        db.execute("update racks set designation = null where shelf_id in "
                   "(select id from shelves where section = 'research')")
        # Box type is structure, not sample data, so it survives a truncate —
        # which meant a box left plain by one test silently changed how the
        # next test's writes behaved.
        db.execute("update boxes set box_type = 'grid', bulk_sample_type = null, "
                   "bulk_tube_count = null, bulk_study = null, bulk_kind = 'tubes', "
                   "bulk_fullness = null")
        db.execute("delete from species where banding_code = 'ZZZZ'")
        db.commit()
    yield


@pytest.fixture
def anon(flask_app):
    """A client that has not signed in."""
    return flask_app.test_client()


# Two fields a raptor tube cannot be saved without any more: a timing for
# blood, and a case number for a new bird. Most tests are about something
# else — positions, IDs, exports — and should not each restate them, so the
# signed-in client fills them in when a test leaves them out. A test about
# the requirement itself uses ``raw_client``, which fills in nothing.
RAPTOR_TUBE_DEFAULTS = {'blood_timing': 'Intake', 'wrmd_number': 'W-TEST'}


class _FillingClient:
    """Wraps the Flask test client; only raptor tube writes are touched."""

    def __init__(self, inner):
        self._inner = inner

    def _fill(self, path, kwargs):
        body = kwargs.get('json')
        if isinstance(body, dict) and path.startswith('/api/raptor/tubes'):
            body = dict(body)
            blood = body.get('sample_type', 'Plasma') in ('Plasma', 'Packed RBCs')
            if blood and 'blood_timing' not in body:
                body['blood_timing'] = RAPTOR_TUBE_DEFAULTS['blood_timing']
            joining = bool(body.get('bird_id'))
            if not joining and not (body.get('wrmd_number') or body.get('vmth_number')) \
                    and 'wrmd_number' not in body and 'vmth_number' not in body:
                body['wrmd_number'] = RAPTOR_TUBE_DEFAULTS['wrmd_number']
            kwargs['json'] = body
        return kwargs

    def post(self, path, **kwargs):
        return self._inner.post(path, **self._fill(path, kwargs))

    def put(self, path, **kwargs):
        return self._inner.put(path, **self._fill(path, kwargs))

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _signed_in(flask_app):
    test_client = flask_app.test_client()
    response = test_client.post('/login', data={'password': TEST_PASSWORD})
    assert response.status_code == 302, 'login should redirect on success'
    return test_client


@pytest.fixture
def client(flask_app):
    """A signed-in client that supplies the raptor tube defaults."""
    return _FillingClient(_signed_in(flask_app))


@pytest.fixture
def raw_client(flask_app):
    """A signed-in client that sends exactly what the test gives it."""
    return _signed_in(flask_app)


@pytest.fixture
def boxes(flask_app):
    """One raptor box and one research box to store things in."""
    from db import get_db

    with flask_app.app_context():
        db = get_db()
        raptor = db.execute(
            "select id, grid_rows, grid_cols from boxes where section = 'raptor' order by id limit 1"
        ).fetchone()
        research = db.execute(
            "select id, grid_rows, grid_cols from boxes where section = 'research' order by id limit 1"
        ).fetchone()
        return {'raptor': dict(raptor), 'research': dict(research)}


@pytest.fixture
def species_id(flask_app):
    from db import get_db

    with flask_app.app_context():
        row = get_db().execute(
            "select id from species where banding_code = 'RTHA'"
        ).fetchone()
        return row['id']
