"""Test fixtures.

These run against a real PostgreSQL database, because almost everything worth
testing here is SQL. Point DATABASE_URL at a scratch database with the
migrations applied; without it the suite skips rather than failing.

    createdb freezer_test
    psql -d freezer_test -f migrations/20260815000000_initial_schema.sql
    psql -d freezer_test -f migrations/20260815000001_seed_reference_data.sql
    DATABASE_URL=postgresql://localhost/freezer_test pytest
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
    return application


@pytest.fixture(autouse=True)
def clean_database(flask_app):
    """Every test starts with an empty freezer but the full structure intact."""
    from db import get_db

    with flask_app.app_context():
        db = get_db()
        db.execute('truncate raptor_tubes, research_tubes, raptor_id_sequence restart identity')
        db.execute("delete from species where banding_code = 'ZZZZ'")
        db.commit()
    yield


@pytest.fixture
def anon(flask_app):
    """A client that has not signed in."""
    return flask_app.test_client()


@pytest.fixture
def client(flask_app):
    """A signed-in client."""
    test_client = flask_app.test_client()
    response = test_client.post('/login', data={'password': TEST_PASSWORD})
    assert response.status_code == 302, 'login should redirect on success'
    return test_client


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
