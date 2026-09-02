# CLIPR Sample Repository and Raptor Biobank

Freezer management for the biorepository: an Eppendorf CryoCube F740hi laid out
as 3 shelves × 6 racks × 7 drawers × 4 boxes, each box a 10×10 grid — 5,040 tube
positions in all.

The upper shelf holds the **raptor plasma biobank**, where each bird gets an
auto-generated tube ID (`RTHA26001` — species, year, sequence). The middle and
lower shelves hold **CLIPR research** samples with free-text sample IDs.

A research box can also be switched to a **plain box**, which holds a list of
samples with no fixed positions — for whirl-paks of tissue and anything else
that has no well to sit in.

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

### 2. Build the schema

Nothing to do by hand. Open the app and it shows a banner:

> **The database needs an update.** 4 updates to apply. **[Update now]**

Click it. That applies everything in `migrations/` and seeds 46 raptor species
plus the full freezer structure (504 boxes, `U1-D1-B1` through `L6-D7-B4`).
The same banner appears after any deploy that adds a migration.

If you would rather do it from a terminal:

```bash
for f in migrations/*.sql; do psql "$DATABASE_URL_UNPOOLED" -f "$f"; done
```

Either way is safe to repeat — every migration is written to be re-runnable,
and `schema_migrations` records what has been applied.

### 3. Set the remaining environment variables

| Variable | Required | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Pooled Postgres connection string (set by the Neon integration) |
| `SECRET_KEY` | yes | Signs session cookies. `python -c 'import secrets; print(secrets.token_hex(32))'` |
| `FREEZER_PASSWORD` | yes | The shared lab password |
| `SESSION_HOURS` | no | Hours before a session expires (default 12) |
| `DB_POOL_MAX` | no | Pooled connections per instance (default 4) |
| `SMTP_USER` | no | Mail account for drop-off alerts — see below |
| `SMTP_PASSWORD` | no | Gmail **App Password**, not the account password |
| `NOTIFY_EMAIL` | no | Where alerts go (default: `SMTP_USER`) |
| `SMTP_HOST` | no | Default `smtp.gmail.com` |
| `SMTP_PORT` | no | Default 587 (STARTTLS); 465 uses implicit TLS |
| `SMTP_FROM` | no | Envelope sender (default: `SMTP_USER`) |

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

If the schema is behind the code it returns 503 and names what is outstanding,
rather than letting the gap surface later as an unexplained error on one page:

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
```

Then start the app and click the update banner.

---

## Tests

The suite runs against a real database, because nearly everything worth testing
here is SQL. Without `DATABASE_URL` it skips rather than failing.

```bash
createdb freezer_test
DATABASE_URL=postgresql://localhost/freezer_test pytest
```

An empty database is enough — the suite applies the migrations itself, which
means the migration path is covered rather than bypassed.

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
  collection.py          Satellite sites and the public drop-off page
  retrieval.py           Retrieval log
  raptor.py              Raptor samples, species
  research.py            Research tubes
  stats.py               Dashboard aggregates
  export.py              Excel/CSV downloads
  support.py             Shared request parsing and the write() transaction wrapper
services/
  migrator.py            Applies pending migrations under an advisory lock
  notify.py              Drop-off alert emails over SMTP
  id_generator.py        RTHA26001-style tube IDs
  stats_service.py       Statistics queries
  export_service.py      Workbook and CSV generation
templates/               Jinja pages
public/static/           CSS, JS and vendored Bootstrap/Chart.js — served by Vercel's CDN
migrations/              Schema and reference data
.github/workflows/       Nightly pg_dump backup
```

### Notes on a few decisions

**Depth is stated, not implied.** The two levels count along different axes:
drawers stack vertically, so `D1` is the top drawer, while the boxes inside a
drawer sit one behind another, so `B1` is the one at the front. The stacking is
visible — the screen draws drawers in a column — but depth is not, and `B4` is
a name rather than a direction, so nothing told you which end of an open drawer
you were looking at.

The box axis is now said four times over: on the cabinet plate, as numbered
columns above each rack with the front one picked out, as a heavier front edge
on every box in that column, and as a badge on the open box reading "front of
the drawer" or "3 of 4 from the front". Tooltips and aria-labels carry the same
wording, so it is neither hover-only nor sighted-only. The column comments in
`migrations/` say the same thing, so the rule survives someone reading only the
schema.

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

**The filter is the query, and the download is the same query.** "Find samples
in the biobank" on the statistics page narrows by species, sample type, sex and
age, shows how many match and where each one is, and hands the same rows to
Excel or CSV — WRMD and VMTH numbers included. The criteria build one SQL
predicate used by all three, so the number on screen is always the number of
rows in the file. A count you can see but not download, or a download that
quietly differs from the count, is worse than no count at all.

The dropdowns are built from what the biobank actually holds, with a tally
beside each option, rather than from the values today's form happens to offer.
That way nothing is listed that would return nothing, and a sample type
recorded before an option existed — or after one was renamed — is still
reachable. The on-screen list stops at 250 rows and says so; the download
never does.

**Statistics count birds, not tubes.** Several tubes from one bird share a base
ID with a `-N` suffix, and the sample counts use `split_part` to collapse them.
`tubes_stored` on the freezer stats is the physical count, used for occupancy.

**The entrypoint lives in `api/`.** Vercel's generic Python runtime only
discovers functions inside an `api/` directory, and framework auto-detection
cannot be relied on. Routing everything through `api/index.py` makes the
deployment independent of the project's framework preset. Flask keeps serving
`/static` itself as well, so a missing CDN route degrades to a slower request
rather than an unstyled page.

**Migrations are applied from the app, not by hand.** A deploy that adds a
column used to need someone to remember to run the SQL, and forgetting took a
page down with an unhelpful error. `services/migrator.py` applies pending
files under a Postgres advisory lock — so parallel cold starts cannot race —
and records them in `schema_migrations`. Nothing runs on import; it happens
when someone clicks the banner. Every migration is written to be re-runnable,
which is also what lets a database created before the tracking table existed
be brought under management by replaying everything.

**The drop-off page has no login, on purpose.** Raptor samples are left in
ordinary freezers at CRC and VMTH before being collected for the -80. Whoever
drops them is standing at a freezer with a phone and does not have the lab
password, so requiring a session would mean the count never gets recorded.
The QR code carries an unguessable per-site token instead. What that protects
is a counter, not specimen records: the worst case is an inflated number the
lab can reset, and the token is compared in constant time and never included
in the site list the rest of the app loads. Replaying migrations does not
rotate the tokens, so printed QR codes keep working.

**The retrieval log outlives the tube.** `retrievals` keeps a snapshot of the
tube ID, box and position alongside a nullable foreign key, so consuming a
tube and deleting its row does not erase the record of who took it out. For a
specimen repository, losing the specimen must never mean losing the history.

A retrieval ends one of two ways, and the app now acts on both. Put the sample
back and its freeze-thaw count goes up, because taking a tube out of a -80
freezer is a thaw whether or not anyone ticks the box. Tick **not going back**
and the tube is deleted: a freezer record that still lists a sample somebody
used up is worse than no record, because it sends the next person hunting for
it. The log entry survives either way.

**Deleting a record is not retrieving a sample.** They look alike and are
opposites: retrieval writes history, deletion erases it. So the delete control
is a quiet grey button rather than a peer of *Log retrieval*, and its
confirmation says what it is for — reconciling the biobank when the database
and the freezer disagree — and points at *Log retrieval* for anything that
actually left the freezer.

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

## Samples waiting at CRC and VMTH

The freezer overview shows a **Samples to collect** panel on the raptor shelf,
with a count and the age of the oldest drop for each satellite site. Age is
what escalates the colour, not count — plasma sitting in an ordinary freezer
degrades. Each site is collected separately, since CRC and VMTH are separate
trips, and collecting marks the drops rather than deleting them so the history
survives.

### Getting an email when someone drops samples off

Set `SMTP_USER`, `SMTP_PASSWORD` and `NOTIFY_EMAIL` and every drop-off sends a
message: how many were just added, how many are now waiting at that site, how
many at the other one, and the age of the oldest at each. Leave them unset and
nothing changes — the feature is entirely optional.

For Gmail the password must be a **16-character App Password**, created at
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
with 2-Step Verification switched on. Google refuses ordinary account
passwords over SMTP, so the account password will only ever produce a 535.

Once it is set, a small bell appears on the **Samples to collect** panel.
Clicking it sends a test message, so the settings can be checked from a desk
rather than by walking to a freezer with a tube.

The send is best-effort and deliberately so. A drop-off that has been recorded
must never fail because a mail server was slow or an app password expired, so
errors are logged and swallowed — the counter in the database is the record and
the email is a courtesy. It is also sent synchronously rather than from a
background thread: a serverless instance is frozen the moment the response goes
out, which would kill a worker mid-handshake often enough to lose messages
without anyone noticing.

To put a QR code on a freezer door: open the overview and click the QR icon on
that site's card. The panel prints a ready-made sign, copies the code to the
clipboard as an image, or saves it as a PNG for a poster or a slide. The URL
contains the site's token, so treat the printed code as the credential it is.

That panel is deliberately not the tube-label sheet. A tube label is scanned
off the screen by Brady Express Labels and carries a Code 128 barcode; this is
a sign a person points a phone camera at. Sharing one dialog between them only
made both harder to read.

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
- **Sample-type reporting.** `sample_type` is recorded, filterable and
  exported, but not charted. A breakdown alongside the age and sex charts
  would show the shape of the collection at a glance.
