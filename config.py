"""Application configuration, sourced from environment variables."""

import os

# ----- Database -----
# Use the *pooled* Neon connection URL for serverless (host contains "-pooler").
# Format: postgresql://<user>:<pw>@ep-<name>-pooler.<region>.aws.neon.tech/<db>?sslmode=require
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# ----- Flask -----
SECRET_KEY = os.environ.get('SECRET_KEY', 'freezer-default-secret-change-me')

# ----- Email (Gmail SMTP) -----
# Requires a Gmail App Password (set up 2FA, then generate one at
# https://myaccount.google.com/apppasswords). Use the 16-char value here.
GMAIL_USER = os.environ.get('GMAIL_USER', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
# Display name + sending address. Gmail requires the address to match GMAIL_USER.
EMAIL_FROM = os.environ.get('EMAIL_FROM', GMAIL_USER)
APP_BASE_URL = os.environ.get('APP_BASE_URL', 'http://localhost:5000')

# ----- Cron auth -----
# Vercel sets this for protected cron endpoints; we verify against the same value.
CRON_SECRET = os.environ.get('CRON_SECRET', '')

# ----- Freezer physical constants -----
NUM_SHELVES = 3
RACKS_PER_SHELF = 6
DRAWERS_PER_RACK = 7
BOXES_PER_DRAWER = 4
DEFAULT_GRID_ROWS = 10
DEFAULT_GRID_COLS = 10

RAPTOR_SHELF_POSITION = 1
RESEARCH_SHELF_POSITIONS = [2, 3]

RAPTOR_ID_SEQ_DIGITS = 3

AGE_OPTIONS = ['Adult', 'Subadult', 'Juvenile', 'Hatch Year', 'After Hatch Year', 'Unknown']
SEX_OPTIONS = ['Male', 'Female', 'Unknown']

# ----- Roles -----
ROLES = ('admin', 'raptor', 'clipr', 'both')
ROLE_LABELS = {
    'admin': 'Administrator',
    'raptor': 'Raptor Biobank',
    'clipr': 'CLIPR Research',
    'both': 'Raptor + CLIPR',
}
