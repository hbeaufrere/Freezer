"""Schema migrations, applied from the app.

Migrations used to be a manual step, which meant deploying a column and
forgetting to add it took the app down with an unhelpful error. This applies
the files in ``migrations/`` instead, guarded so it is safe on Vercel:

  * A Postgres advisory lock serialises the run, so parallel cold starts
    cannot apply the same file twice.
  * ``schema_migrations`` records what has run.
  * Every migration is written to be re-runnable anyway, so a database that
    predates the tracking table can be brought under management by simply
    replaying everything.

Nothing runs on import. Migrations are applied when someone asks, either from
the banner in the app or by POSTing to /api/admin/migrate.
"""

import logging
import os

log = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'migrations'
)

# Arbitrary but fixed: identifies this app's migration lock.
_LOCK_KEY = 8402_2851

_TRACKING_TABLE = """
create table if not exists schema_migrations (
    filename   text primary key,
    applied_at timestamptz not null default now()
)
"""


def available():
    """Every migration filename on disk, oldest first."""
    if not os.path.isdir(MIGRATIONS_DIR):
        return []
    return sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql'))


def applied(db):
    """Filenames already recorded as applied."""
    db.execute(_TRACKING_TABLE)
    rows = db.execute('select filename from schema_migrations').fetchall()
    return {r['filename'] for r in rows}


def pending(db):
    """Migrations on disk that have not been recorded as applied."""
    done = applied(db)
    return [name for name in available() if name not in done]


def apply_pending(db):
    """Run every pending migration inside an advisory lock.

    Returns the list of filenames applied. Raises on the first failure, having
    rolled back that file — each migration runs in its own transaction so a
    later failure does not undo earlier successes.
    """
    # Blocks rather than skipping: a second instance waits, then finds nothing
    # pending, which is the outcome we want.
    db.execute('select pg_advisory_lock(%s)', (_LOCK_KEY,))
    applied_now = []
    try:
        db.execute(_TRACKING_TABLE)
        db.commit()

        for name in pending(db):
            path = os.path.join(MIGRATIONS_DIR, name)
            with open(path, encoding='utf-8') as handle:
                sql = handle.read()
            try:
                db.execute(sql)
                db.execute(
                    'insert into schema_migrations (filename) values (%s) '
                    'on conflict (filename) do nothing',
                    (name,),
                )
                db.commit()
                applied_now.append(name)
                log.info('Applied migration %s', name)
            except Exception:
                db.rollback()
                log.exception('Migration %s failed', name)
                raise
    finally:
        try:
            db.execute('select pg_advisory_unlock(%s)', (_LOCK_KEY,))
            db.commit()
        except Exception:
            log.exception('Could not release the migration lock')

    return applied_now
