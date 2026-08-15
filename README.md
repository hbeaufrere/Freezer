# CLIPR Sample Repository and Raptor Biobank

Freezer management for the biorepository: an Eppendorf CryoCube F740hi laid out
as 3 shelves × 6 racks × 7 drawers × 4 boxes, each box a 10×10 grid — 5,040 tube
positions in all.

The upper shelf holds the **raptor plasma biobank**, where each bird gets an
auto-generated tube ID (`RTHA26001` — species, year, sequence). The middle and
lower shelves hold **CLIPR research** samples with free-text sample IDs.

Flask + PostgreSQL, running as a Vercel Function against a Neon database.

Nothing here is tied to a particular Postgres host — the app speaks plain SQL
over psycopg, so any Postgres will do. Neon is the default because its free
tier covers this workload comfortably and it provisions straight from the
Vercel account the app already deploys to.

---

## Setting it up

### 1. Create the database

From the project directory, with the Vercel CLI:

```bash
vercel install neon
```

Or add Neon from the **Storage** tab of the Vercel dashboard. Either way the
integration provisions a database and sets the connection variables on the
project automatically — including `DATABASE_URL` (pooled) and
`DATABASE_URL_UNPOOLED` (direct).

Confirm that `DATABASE_URL` is the **pooled** one; its host contains `-pooler`.
Serverless functions open far more short-lived connections than a direct
Postgres endpoint can absorb.

### 2. Apply the migrations

```bash
psql "$DATABASE_URL_UNPOOLED" -f migrations/20260815000000_initial_schema.sql
psql "$DATABASE_URL_UNPOOLED" -f migrations/20260815000001_seed_reference_data.sql
```

Or paste each file into Neon's SQL Editor, in filename order. They are
idempotent, so re-running them is safe.

That creates the schema and seeds 46 raptor species plus the full freezer
structure (504 boxes, labelled `U1-D1-B1` through `L6-D7-B4`).

### 3. Set the remaining environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Pooled Postgres connection string (set by the Neon integration) |
| `SECRET_KEY` | yes | Signs session cookies. `python -c 'import secrets; print(secrets.token_hex(32))'` |
| `FREEZER_PASSWORD` | yes | The shared lab password |
| `SESSION_HOURS` | no | Hours before a session expires (default 12) |
| `DB_POOL_MAX` | no | Pooled connections per instance (default 4) |

There are no fallback defaults for the three required variables — the app
refuses to start without them, so a placeholder secret can never end up
guarding real data.

### 4. Deploy

Import the repository at [vercel.com/new](https://vercel.com/new), add those
environment variables, and deploy. `api/index.py` is the entrypoint Vercel
runs, and `vercel.json` rewrites every path onto it; `requirements.txt` is
installed automatically.

Check `/api/health` afterwards — it returns `{"status": "ok", "database":
"connected", "schema": "current"}` once everything is in place.

If a migration has been missed it returns 503 and names the files still to
run, rather than letting the gap surface later as an unexplained error on one
page:

```json
{"status": "error", "schema": "out of date",
 "pending_migrations": ["20260815000002_add_sample_type.sql"]}
```

### 5. Turn on backups

`.github/workflows/backup.yml` runs `pg_dump` nightly and keeps the result as a
workflow artifact for 90 days. To enable it, add one repository secret under
**Settings → Secrets and variables → Actions**:

- `DATABASE_URL_UNPOOLED` — the **direct** connection string, not the pooled
  one. `pg_dump` needs a real session for its consistent snapshot and will not
  work reliably through a transaction pooler.

Run it once by hand from the Actions tab to check it works. Artifacts expire
after 90 days, so download one occasionally if you want a long-term archive.

### A note on idle databases

Neon suspends compute after a few minutes of inactivity and wakes it on the
next connection, so the first request after a quiet spell takes about a second.
That is why `connect_timeout` is set generously in `db.py`. It is also the
reason Neon suits this app better than a free tier that *pauses* projects
outright after a week and needs manual intervention to come back — a freezer
tool may sit untouched for a fortnight and then be needed straight away.

---

## Running it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env      # then fill in the three required values
python app.py             # http://127.0.0.1:5000
```

Set `FLASK_ENV=development` in `.env` so session cookies work over plain HTTP.

You can point `DATABASE_URL` at the hosted database, or run Postgres locally:

```bash
createdb freezer
psql -d freezer -f migrations/20260815000000_initial_schema.sql
psql -d freezer -f migrations/20260815000001_seed_reference_data.sql
```

---

## Tests

The suite runs against a real database, because nearly everything worth testing
here is SQL. Without `DATABASE_URL` it skips rather than failing.

```bash
createdb freezer_test
psql -d freezer_test -f migrations/20260815000000_initial_schema.sql
psql -d freezer_test -f migrations/20260815000001_seed_reference_data.sql

DATABASE_URL=postgresql://localhost/freezer_test pytest
```

Each test truncates the tube tables first, so the freezer structure survives but
no sample data leaks between tests. **Never point this at the production
database** — it empties the tube tables on every test.

---

## How it fits together

```
api/index.py             Vercel entrypoint — re-exports the app from app.py
app.py                   Flask app factory, auth, error handling, page routes
db.py                    Connection pool, request-scoped connections, error translation
routes/
  freezer.py             Shelves, racks, drawers, boxes
  retrieval.py           Retrieval log
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
migrations/              Schema and reference data
.github/workflows/       Nightly pg_dump backup
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

**The entrypoint lives in `api/`.** Vercel's generic Python runtime only
discovers functions inside an `api/` directory, and framework auto-detection
cannot be relied on. Routing everything through `api/index.py` makes the
deployment independent of the project's framework preset. Flask keeps serving
`/static` itself as well, so a missing CDN route degrades to a slower request
rather than an unstyled page.

**The retrieval log outlives the tube.** `retrievals` keeps a snapshot of the
tube ID, box and position alongside a nullable foreign key, so consuming a
tube and deleting its row does not erase the record of who took it out. For a
specimen repository, losing the specimen must never mean losing the history.
Logging a retrieval also counts one freeze-thaw cycle, because taking a tube
out of a -80 freezer is a thaw whether or not anyone ticks the box.

**Labels go out by barcode, not by print driver.** There is no workable web
print path to a Brady M211, and the Bluetooth attempt never printed anything.
Instead the tube's ID is rendered on screen as a barcode; Brady Express Labels
scans it off the monitor and fills the label under the Vial preset. Both
Code 128 and QR are offered because scanner implementations differ — the app
remembers which one you used last. Verified by decoding the rendered output:
both symbologies read back the exact tube ID.

**The palette is UC Davis Aggie Blue and Gold.** Light mode leads with Aggie Blue (#022851) because gold cannot hold text contrast on white; dark mode inverts it, with gold as the accent over a navy ground. The twelve species colours in the box grid stay outside the brand palette — categorical encoding needs hues that separate at 34px, which two brand colours cannot provide.

**Assets are vendored, not loaded from a CDN.** Bootstrap and Chart.js live in
`public/static/vendor/`, so the app has no third-party runtime dependency and
works on a lab network that blocks outside requests.

---

## Worth doing next

- **Real accounts.** One shared password means no per-person access and no way
  to revoke it when someone leaves. A hosted identity provider would replace it
  with magic-link sign-in and no password handling on our side — Clerk and
  Auth0 both install from the Vercel Marketplace and have free tiers well above
  a lab-sized team.
- **An audit trail.** Deletes are permanent and anonymous. For a specimen
  repository, `created_by` / `updated_by` columns and a `deleted_at` soft delete
  would make "who removed RTHA26014, and when" an answerable question.
- **Retrieval log export.** The log is searchable and paginated in the browser
  but has no Excel/CSV route yet, unlike the two sample tables.
- **Sample-type reporting.** `sample_type` is recorded and exported but not yet
  charted. A breakdown on the statistics page would answer "how much liver do
  we hold" without an export.
