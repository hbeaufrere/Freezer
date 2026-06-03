# Vercel + Supabase Deployment Guide

This branch hosts the Vercel-targeted version of the app. The `main` branch is
unchanged and still runs on PythonAnywhere.

## Stack

- **Hosting**: Vercel (Python serverless functions)
- **Database**: Supabase Postgres (transaction pooler, port 6543)
- **Email**: Resend (transactional, free tier 3000/month)
- **Auth**: custom — bcrypt-hashed passwords, Flask signed-cookie sessions, roles in the `users` table

## One-time setup

### 1. Supabase

1. Create a new project at https://supabase.com (free tier is fine).
2. In **Project Settings -> Database -> Connection string -> Transaction pooler**, copy the URL. It looks like:
   ```
   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```
3. Keep this — it goes into `DATABASE_URL`.

### 2. Resend

1. Sign up at https://resend.com.
2. Create an API key under **API Keys**.
3. For production, verify a sending domain and use `EMAIL_FROM=Your Lab <noreply@yourlab.org>`.
   For testing without a domain, you can leave `EMAIL_FROM` unset and Resend will use
   `onboarding@resend.dev` (only delivers to your account email).

### 3. Bootstrap the database

Locally, with `DATABASE_URL` exported, run:

```bash
pip install -r requirements.txt
export DATABASE_URL='postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres'
python init_db.py
```

This applies the schema, seeds the species list, creates the default 3x6x7x4 freezer
structure, and creates the first admin user (it'll prompt for email/password).

### 4. Deploy to Vercel

```bash
npm i -g vercel    # if needed
vercel link        # link to a Vercel project
vercel env add DATABASE_URL          # paste pooler URL
vercel env add SECRET_KEY            # 32+ random characters
vercel env add RESEND_API_KEY        # your Resend API key
vercel env add EMAIL_FROM            # e.g. "CLIPR Biobank <noreply@yourlab.org>"
vercel env add APP_BASE_URL          # https://your-project.vercel.app
vercel env add CRON_SECRET           # 32+ random characters; used by the keepalive cron
vercel deploy --prod
```

Vercel sets `CRON_SECRET` on the `Authorization` header of cron invocations
automatically when you define `CRON_SECRET` as an env var — the `cron.keepalive`
route validates it.

### 5. (Optional) Update `APP_BASE_URL`

The login link in invite emails points at `${APP_BASE_URL}/login`. After your first
deploy, set `APP_BASE_URL` to the real domain and re-deploy.

## Environment variables

| Variable          | Required | Notes                                              |
|-------------------|----------|----------------------------------------------------|
| `DATABASE_URL`    | yes      | Supabase transaction pooler URL (port 6543)        |
| `SECRET_KEY`      | yes      | Flask session signing key (32+ random chars)       |
| `RESEND_API_KEY`  | yes (prod) | Without this, temp passwords print to logs       |
| `EMAIL_FROM`      | yes (prod) | `Your Lab <noreply@yourlab.org>`                 |
| `APP_BASE_URL`    | yes      | Public URL, used in invite emails                  |
| `CRON_SECRET`     | yes      | Vercel-set bearer token validated by keepalive    |

## Cron jobs

`vercel.json` defines a single cron:

- `/api/cron/keepalive` every Monday at 06:00 UTC — runs `SELECT now()` to reset
  the Supabase free-tier 7-day pause timer. Add more crons here if needed
  (paid Vercel allows multiple).

## Roles & access

| Role     | Can see / edit                                                                  |
|----------|---------------------------------------------------------------------------------|
| `admin`  | Everything, plus `/admin/users` for user management                             |
| `raptor` | Freezer view, raptor tubes, raptor stats/export                                  |
| `clipr`  | Freezer view, research tubes, research stats/export                              |
| `both`   | Freezer view, raptor + research tubes, both stats/exports (no user mgmt)         |

Freezer structure (shelves/racks/drawers/boxes) is read-only for non-admins.
Creating, editing, or deleting boxes is admin-only.

## User onboarding flow

1. Admin opens `/admin/users` and clicks **Invite user**.
2. Enters email, optional full name, and role.
3. Server generates a 12-character random password, hashes it, and emails it via Resend.
4. On first sign-in the user is forced to set a new password.
5. If email delivery fails, the modal in the admin UI shows the temp password as a
   one-time fallback so the admin can share it through another secure channel.

To reset a password, the admin clicks the reset icon next to a user — same flow,
new temp password.

## Local development

```bash
export DATABASE_URL='postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres'
export SECRET_KEY='dev-not-secret'
# Resend optional in dev — without it, emails print to stdout
python app.py
```

Then visit http://localhost:5000/login.

## Differences from the PythonAnywhere version (`main`)

- SQLite -> Supabase Postgres
- Shared password (`FREEZER_PASSWORD`) -> per-user accounts with bcrypt + roles
- Auto-migration on startup -> explicit `init_db.py` bootstrap
- `wsgi.py` -> `api/index.py` (Vercel entry)
- No `init_db.py` species list helper -> same script also creates first admin
- Refreshed UI (Inter font, modern color palette, role-aware nav)
- No data import — empty DB is assumed
