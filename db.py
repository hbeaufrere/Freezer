"""Postgres connection helpers.

One connection per request via Flask's `g`. Designed for Supabase's
transaction pooler (port 6543), so prepared statements are disabled.
"""

import psycopg
from psycopg.rows import dict_row
from flask import g

import config


def _connect():
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Configure it to your Supabase pooler URL."
        )
    return psycopg.connect(
        config.DATABASE_URL,
        row_factory=dict_row,
        prepare_threshold=None,
        autocommit=False,
    )


def get_db():
    """Return the request-scoped Postgres connection."""
    if 'db' not in g:
        g.db = _connect()
    return g.db


def close_db(e=None):
    """Roll back uncommitted work and close the connection at request end."""
    db = g.pop('db', None)
    if db is None:
        return
    try:
        if e is not None:
            db.rollback()
    finally:
        db.close()


def fetch_one(query, params=()):
    return get_db().execute(query, params).fetchone()


def fetch_all(query, params=()):
    return get_db().execute(query, params).fetchall()
