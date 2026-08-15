"""PostgreSQL access layer.

Connections come from a small process-wide pool. On Vercel every function
instance keeps its own pool, so the pool stays deliberately small — the
provider's connection pooler is what actually multiplexes those onto Postgres.

Routes use the connection directly, the same shape the sqlite3 version used:

    rows = get_db().execute("select ... where id = %s", (box_id,)).fetchall()

Rows come back as dicts, so ``dict(row)`` and ``row['column']`` both work.
"""

import os
import threading

import psycopg
from flask import g
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool = None
# Pool creation is lazy, and the pages fire several API calls at once. Without
# this, concurrent first requests each see `_pool is None` and build their own
# pool; connections then get handed back to a pool they did not come from,
# which psycopg_pool rejects outright.
_pool_lock = threading.Lock()


def database_url():
    """The Postgres connection string, or a clear error explaining what's missing."""
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise RuntimeError(
            'DATABASE_URL is not set. Use your provider\'s *pooled* connection '
            'string — on Neon the host contains "-pooler".'
        )
    return url


def get_pool():
    global _pool
    if _pool is not None:
        return _pool

    with _pool_lock:
        # Re-check inside the lock: another thread may have won the race.
        if _pool is not None:
            return _pool
        _pool = ConnectionPool(
            conninfo=database_url(),
            min_size=0,
            max_size=int(os.environ.get('DB_POOL_MAX', '4')),
            max_idle=60,
            timeout=10,
            # Serverless instances get frozen between requests, so verify a
            # connection is still alive before handing it out.
            check=ConnectionPool.check_connection,
            kwargs={
                'row_factory': dict_row,
                # Transaction-mode poolers multiplex sessions and cannot keep
                # server-side prepared statements around.
                'prepare_threshold': None,
                # Neon suspends idle compute, so the first connection after a
                # quiet spell has to wait for it to wake.
                'connect_timeout': 15,
            },
            name='freezer',
            open=True,
        )
    return _pool


def get_db():
    """The connection for the current request."""
    if 'db' not in g:
        g.db = get_pool().getconn()
    return g.db


def close_db(exc=None):
    """Return the request's connection to the pool, discarding uncommitted work."""
    conn = g.pop('db', None)
    if conn is None:
        return
    try:
        # Routes commit explicitly. Anything still open at teardown was either
        # an error path or a bug — either way it should not be written.
        conn.rollback()
    except psycopg.Error:
        pass  # Broken connection; the pool will discard it.

    try:
        get_pool().putconn(conn)
    except ValueError:
        # Belt and braces: if this connection somehow came from a different
        # pool, closing it is better than losing the request to a 500.
        conn.close()


def insert_returning_id(db, sql, params):
    """Run an INSERT ending in ``returning id`` and give back the new id."""
    return db.execute(sql, params).fetchone()['id']


# ------------------------------------------------------------
# Error translation
# ------------------------------------------------------------

class ApiError(Exception):
    """An error that is safe to show the user, with an HTTP status."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def describe_db_error(exc):
    """Turn a psycopg error into something a lab tech can act on.

    Returns None for errors with no good plain-language form, so the caller
    logs the detail server-side and shows a generic message instead of
    leaking table and column names to the browser.
    """
    if isinstance(exc, psycopg.errors.UniqueViolation):
        constraint = getattr(getattr(exc, 'diag', None), 'constraint_name', '') or ''
        if 'row_pos' in constraint or constraint.endswith('_box_id_row_pos_col_pos_key'):
            return 'That position already holds a tube.'
        if 'tube_id' in constraint:
            return 'That tube ID is already in use.'
        if 'banding_code' in constraint:
            return 'A species with that banding code already exists.'
        return 'That record already exists.'
    if isinstance(exc, psycopg.errors.ForeignKeyViolation):
        return 'That box or species no longer exists. Reload the page and try again.'
    if isinstance(exc, psycopg.errors.CheckViolation):
        constraint = getattr(getattr(exc, 'diag', None), 'constraint_name', '') or ''
        if 'banding_code' in constraint:
            return 'Banding codes must be exactly four letters, A-Z.'
        if '_ft_valid' in constraint:
            return 'Freeze-thaw cycles cannot be negative.'
        return 'One of those values is out of range.'
    if isinstance(exc, psycopg.errors.NotNullViolation):
        column = getattr(getattr(exc, 'diag', None), 'column_name', '') or 'A required field'
        return f'{column} is required.'
    return None
