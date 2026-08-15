# CLIPR Repository / Raptor Biobank

Freezer management for the biorepository: an Eppendorf CryoCube F740hi laid out
as 3 shelves × 6 racks × 7 drawers × 4 boxes, each box a 10×10 grid — 5,040 tube
positions in all.

The upper shelf holds the **raptor plasma biobank**, where each bird gets an
auto-generated tube ID (`RTHA26001` — species, year, sequence). The middle and
lower shelves hold **CLIPR research** samples with free-text sample IDs.

Flask + PostgreSQL, running as a Vercel Function against a Supabase database.

---

## Setting it up

### 1. Create the Supabase database

Create a project at [supabase.com](https://supabase.com), then apply the two
migrations in `supabase/migrations/` — either with the CLI:

```bash
supabase link --project-ref YOUR_PROJECT_REF
supabase db push
```

or by pasting each file into the SQL Editor, in filename order. They are
idempotent, so re-running them is safe.

That creates the schema and seeds 46 raptor species plus the full freezer
structure (504 boxes, labelled `U1-D1-B1` through `L6-D7-B4`).

### 2. Get the connection string

In the Supabase dashboard: **Connect → Transaction pooler**. Use that one —
port **6543**, not the direct connection on 5432. Serverless functions open far
more short-lived connections than a direct Postgres connection can absorb.

### 3. Set the environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Supabase transaction pooler string, port 6543 |
| `SECRET_KEY` | yes | Signs session cookies. `python -c 'import secrets; print(secrets.token_hex(32))'` |
| `FREEZER_PASSWORD` | yes | The shared lab password |
| `SESSION_HOURS` | no | Hours before a session expires (default 12) |
| `DB_POOL_MAX` | no | Pooled connections per instance (default 4) |

There are no fallback defaults for the three required variables — the app
refuses to start without them, so a placeholder secret can never end up
guarding real data.

### 4. Deploy

Import the repository at [vercel.com/new](https://vercel.com/new), add those
environment variables, and deploy. Vercel detects Flask from the module-level
`app` in `app.py` and installs `requirements.txt`.

Check `/api/health` afterwards — it returns `{"status": "ok", "database":
"connected"}` once the database is reachable.

---

## Running it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then fill in the three required values
python app.py             # http://127.0.0.1:5000
```

Set `FLASK_ENV=development` in `.env` so session cookies work over plain HTTP.

You can point `DATABASE_URL` at Supabase directly, or run Postgres locally:

```bash
createdb freezer
psql -d freezer -f supabase/migrations/20260815000000_initial_schema.sql
psql -d freezer -f supabase/migrations/20260815000001_seed_reference_data.sql
```

---

## Tests

The suite runs against a real database, because nearly everything worth testing
here is SQL. Without `DATABASE_URL` it skips rather than failing.

```bash
createdb freezer_test
psql -d freezer_test -f supabase/migrations/20260815000000_initial_schema.sql
psql -d freezer_test -f supabase/migrations/20260815000001_seed_reference_data.sql

DATABASE_URL=postgresql://localhost/freezer_test pytest
```

Each test truncates the tube tables first, so the freezer structure survives but
no sample data leaks between tests. **Never point this at the production
database** — it empties the tube tables on every test.

---

## How it fits together

```
app.py                   Flask app factory, auth, error handling, page routes
db.py                    Connection pool, request-scoped connections, error translation
routes/
  freezer.py             Shelves, racks, drawers, boxes
  raptor.py              Raptor samples, species
  research.py            Research tubes
  stats.py               Dashboard aggregates
  export.py              Excel/CSV downloads
  support.py             Shared request parsing and the write() transaction wrapper
services/
  id_generator.py        RTHA26001-style tube IDs
  stats_service.py       Statistics queries
  export_service.py      Workbook and CSV generation
templates/               Jinja pages
public/static/           CSS, JS and vendored Bootstrap/Chart.js — served by Vercel's CDN
supabase/migrations/     Schema and reference data
```

### Notes on a few decisions

**One query per level, not per node.** `/api/freezer` builds the whole tree from
four flat queries assembled in Python. The obvious nested-loop version issues
about 148 queries, which is invisible against a local file and adds seconds of
latency against a hosted database.

**Tube IDs are claimed atomically.** `raptor_id_sequence` is incremented with a
single upsert that returns the new value, so simultaneous submissions get
consecutive IDs instead of colliding. The row stays locked until the transaction
commits, so a failed insert releases the number rather than burning it.

**Searches use `ILIKE`.** Postgres `LIKE` is case-sensitive where SQLite's was
not; `ILIKE` keeps `rtha` finding `RTHA26001`. User wildcards are escaped, so
searching `%` matches a literal percent sign.

**Statistics count birds, not tubes.** Several tubes from one bird share a base
ID with a `-N` suffix, and the sample counts use `split_part` to collapse them.
`tubes_stored` on the freezer stats is the physical count, used for occupancy.

**Assets are vendored, not loaded from a CDN.** Bootstrap and Chart.js live in
`public/static/vendor/`, so the app has no third-party runtime dependency and
works on a lab network that blocks outside requests.

**Row level security is on with no policies.** The app connects as `postgres`,
which bypasses RLS, but enabling it closes off Supabase's auto-generated
PostgREST API so the anon and authenticated keys cannot read specimen records.

---

## Worth doing next

- **Real accounts.** One shared password means no per-person access and no way
  to revoke it when someone leaves. Supabase Auth with magic links would replace
  it without any password handling on our side.
- **An audit trail.** Deletes are permanent and anonymous. For a specimen
  repository, `created_by` / `updated_by` columns and a `deleted_at` soft delete
  would make "who removed RTHA26014, and when" an answerable question.
- **Label printing over Bluetooth.** `printer.js` has the hooks, but the Brady
  Web SDK is not bundled, so labels currently go through the browser print
  dialog. That works everywhere; direct BLE printing needs the SDK added.
