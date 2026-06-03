"""Postgres connection helpers.

Uses a small psycopg connection pool so warm Vercel function instances
reuse connections to Neon across requests (cutting per-request TCP/TLS
handshake to zero on warm hits).
"""

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from flask import g

import config

_pool = None


def _get_pool():
    """Lazily create the pool on first use."""
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Configure it to your Neon pooled URL."
            )
        _pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=4,
            timeout=15,
            kwargs={
                "row_factory": dict_row,
                "prepare_threshold": None,
                "autocommit": False,
            },
        )
    return _pool


def get_db():
    """Return the request-scoped Postgres connection (checked out of the pool)."""
    if 'db' not in g:
        g.db = _get_pool().getconn()
    return g.db


def close_db(e=None):
    """Return the connection to the pool at request end (rolling back on error)."""
    db = g.pop('db', None)
    if db is None:
        return
    try:
        if e is not None:
            db.rollback()
    finally:
        try:
            _get_pool().putconn(db)
        except Exception:
            try:
                db.close()
            except Exception:
                pass


def fetch_one(query, params=()):
    return get_db().execute(query, params).fetchone()


def fetch_all(query, params=()):
    return get_db().execute(query, params).fetchall()
