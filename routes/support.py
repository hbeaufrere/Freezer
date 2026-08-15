"""Shared helpers for the API blueprints."""

import logging
from contextlib import contextmanager
from datetime import date

import psycopg
from flask import request

from db import ApiError, describe_db_error

log = logging.getLogger(__name__)


def json_body():
    """The request's JSON object, or a clear error if it isn't one."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError('Expected a JSON object in the request body.')
    return data


def require(data, *fields):
    """Raise unless every named field is present and non-empty."""
    missing = [name for name in fields if data.get(name) in (None, '')]
    if missing:
        raise ApiError(f"Missing required field: {', '.join(missing)}")


def as_int(data, field, minimum=None, maximum=None, default=None):
    """Read an integer field, rejecting values outside the allowed range."""
    raw = data.get(field, default)
    if raw is None:
        raise ApiError(f'{field} is required.')
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError(f'{field} must be a whole number.') from None
    if minimum is not None and value < minimum:
        raise ApiError(f'{field} must be at least {minimum}.')
    if maximum is not None and value > maximum:
        raise ApiError(f'{field} must be no more than {maximum}.')
    return value


def text(data, field, default=''):
    """Read a text field, trimmed, treating null as the default."""
    value = data.get(field, default)
    return value.strip() if isinstance(value, str) else default


def as_date(data, field, required=False):
    """Read an ISO date field as a ``date``, rejecting anything malformed.

    Parsing here rather than handing the string to Postgres means a bad date
    fails with a message about the field rather than a database error.
    """
    raw = data.get(field)
    if raw in (None, ''):
        if required:
            raise ApiError(f'{field} is required.')
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        raise ApiError(f'{field} must be a date in YYYY-MM-DD format.') from None


def like_pattern(query):
    """A contains-pattern for ILIKE, with the user's wildcards taken literally."""
    escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


@contextmanager
def write(db):
    """Wrap a write so it commits on success and reports failures safely.

    Database errors become messages a lab tech can act on. Anything without a
    plain-language form is logged server-side and reported generically, so
    table and column names never reach the browser.
    """
    try:
        yield
        db.commit()
    except ApiError:
        db.rollback()
        raise
    except psycopg.Error as exc:
        db.rollback()
        friendly = describe_db_error(exc)
        if friendly:
            raise ApiError(friendly) from exc
        log.exception('Database write failed on %s %s', request.method, request.path)
        raise ApiError('Could not save that change. Please try again.', 500) from exc


def one_or_404(row, what='Record'):
    """Return the row, or raise a 404 if the query found nothing."""
    if row is None:
        raise ApiError(f'{what} not found.', 404)
    return row
