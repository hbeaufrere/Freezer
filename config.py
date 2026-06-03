"""Application configuration, sourced from environment variables."""

import os

# ----- Database -----
# Use Supabase transaction pooler URL (port 6543) for serverless.
# Format: postgresql://postgres.<ref>:[password]@aws-0-<region>.pooler.supabase.com:6543/postgres
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# ----- Flask -----
SECRET_KEY = os.environ.get('SECRET_KEY', 'freezer-default-secret-change-me')

# ----- Email (Resend) -----
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'CLIPR Biobank <onboarding@resend.dev>')
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
