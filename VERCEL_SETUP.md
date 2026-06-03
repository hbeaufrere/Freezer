# Vercel + Supabase Deployment Guide

This branch hosts the Vercel-targeted version of the app. The `main` branch is
unchanged and still runs on PythonAnywhere.

## Stack

- **Hosting**: Vercel (Python serverless functions)
- **Database**: Supabase Postgres (transaction pooler, port 6543)
- **Email**: Gmail SMTP (your own Gmail account, via an App Password)
- **Auth**: custom — bcrypt-hashed passwords, Flask signed-cookie sessions, roles in the `users` table

## Environment variables

| Variable             | Required | Notes                                              |
|----------------------|----------|----------------------------------------------------|
| `DATABASE_URL`       | yes      | Supabase transaction pooler URL (port 6543)        |
| `SECRET_KEY`         | yes      | Flask session signing key (32+ random chars)       |
| `GMAIL_USER`         | yes      | Your full Gmail address (e.g. `you@gmail.com`)     |
| `GMAIL_APP_PASSWORD` | yes      | 16-char Gmail App Password (not your login pw)     |
| `EMAIL_FROM`         | optional | `"CLIPR Biobank <you@gmail.com>"` — defaults to `GMAIL_USER` |
| `APP_BASE_URL`       | yes      | Public URL, used in invite emails                  |
| `CRON_SECRET`        | yes      | Bearer token validated by the keepalive cron       |

## Roles & access

| Role     | Can see / edit                                                          |
|----------|-------------------------------------------------------------------------|
| `admin`  | Everything, plus `/admin/users` for user management                     |
| `raptor` | Freezer view, raptor tubes, raptor stats/export                          |
| `clipr`  | Freezer view, research tubes, research stats/export                      |
| `both`   | Freezer view, raptor + research tubes, both stats/exports (no user mgmt) |

Freezer structure (shelves/racks/drawers/boxes) is read-only for non-admins.
Creating, editing, or deleting boxes is admin-only.

## User onboarding flow

1. Admin opens `/admin/users` and clicks **Invite user**.
2. Enters email, optional full name, and role.
3. Server generates a 12-character random password, hashes it, and emails it via Gmail.
4. On first sign-in the user is forced to set a new password.
5. If email delivery fails, the modal in the admin UI shows the temp password as a
   one-time fallback so the admin can share it through another secure channel.

To reset a password, the admin clicks the reset icon next to a user — same flow,
new temp password.

## Cron jobs

`vercel.json` defines a single cron:

- `/api/cron/keepalive` every Monday at 06:00 UTC — runs `SELECT now()` to reset
  the Supabase free-tier 7-day pause timer. Add more crons here if needed
  (paid Vercel allows multiple).

## Local development

```bash
export DATABASE_URL='postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres'
export SECRET_KEY='dev-not-secret'
# Gmail is optional in dev — without it, emails print to stdout
export GMAIL_USER='you@gmail.com'
export GMAIL_APP_PASSWORD='abcd efgh ijkl mnop'
python app.py
```

Then visit http://localhost:5000/login.

## Differences from the PythonAnywhere version (`main`)

- SQLite -> Supabase Postgres
- Shared password (`FREEZER_PASSWORD`) -> per-user accounts with bcrypt + roles
- Auto-migration on startup -> explicit `init_db.py` bootstrap
- `wsgi.py` -> `api/index.py` (Vercel entry)
- Refreshed UI (Inter font, modern color palette, role-aware nav)
- No data import — empty DB is assumed
