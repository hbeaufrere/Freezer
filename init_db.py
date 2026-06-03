#!/usr/bin/env python3
"""Initialize the Supabase Postgres database for the Freezer app.

Run locally once after creating a fresh Supabase project:

    DATABASE_URL='postgresql://...' python init_db.py

What it does:
  1. Applies schema.sql (idempotent — uses CREATE TABLE IF NOT EXISTS).
  2. Seeds the raptor species list from seed_species.sql.
  3. Seeds the default 3x6x7x4 freezer structure if empty.
  4. Creates the first admin user (prompts for email if none exists).
"""

import argparse
import getpass
import os
import sys

import psycopg
from psycopg.rows import dict_row

# Make sure local imports work when running this script directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from auth import hash_password, generate_temp_password  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _read(path):
    with open(os.path.join(BASE_DIR, path), 'r') as f:
        return f.read()


def _apply_schema(conn):
    print("Applying schema.sql...")
    conn.execute(_read('schema.sql'))


def _seed_species(conn):
    print("Seeding species list...")
    conn.execute(_read('seed_species.sql'))


def _seed_freezer_structure(conn):
    count = conn.execute("SELECT COUNT(*) AS c FROM shelves").fetchone()['c']
    if count > 0:
        print(f"Freezer structure already present ({count} shelves). Skipping.")
        return

    print("Seeding default freezer structure (3 shelves x 6 racks x 7 drawers x 4 boxes)...")

    raptor_rack_designations = {
        1: 'RTHA / RSHA / SWHA',
        2: 'COHA / WTKI',
        3: 'GHOW / ABOW',
        4: 'WESO / Other Owls',
        5: 'AMKE / TUVU',
        6: 'Other Species',
    }

    shelves = [
        ('Upper Shelf', 1, 'raptor'),
        ('Middle Shelf', 2, 'research'),
        ('Lower Shelf', 3, 'research'),
    ]

    for shelf_name, shelf_pos, section in shelves:
        shelf_id = conn.execute(
            "INSERT INTO shelves (name, position, section) VALUES (%s, %s, %s) RETURNING id",
            (shelf_name, shelf_pos, section)
        ).fetchone()['id']

        shelf_prefix = {1: 'U', 2: 'M', 3: 'L'}[shelf_pos]

        for rack_pos in range(1, 7):
            rack_label = f"Rack {shelf_prefix}{rack_pos}"
            designation = raptor_rack_designations.get(rack_pos) if section == 'raptor' else None
            rack_id = conn.execute(
                "INSERT INTO racks (shelf_id, position, label, designation) VALUES (%s, %s, %s, %s) RETURNING id",
                (shelf_id, rack_pos, rack_label, designation)
            ).fetchone()['id']

            for drawer_pos in range(1, 8):
                drawer_label = f"{shelf_prefix}{rack_pos}-D{drawer_pos}"
                drawer_id = conn.execute(
                    "INSERT INTO drawers (rack_id, position, label) VALUES (%s, %s, %s) RETURNING id",
                    (rack_id, drawer_pos, drawer_label)
                ).fetchone()['id']

                for box_pos in range(1, 5):
                    box_label = f"{shelf_prefix}{rack_pos}-D{drawer_pos}-B{box_pos}"
                    conn.execute(
                        "INSERT INTO boxes (drawer_id, position, label, grid_rows, grid_cols, section) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (drawer_id, box_pos, box_label, 10, 10, section)
                    )


def _create_admin(conn, email=None, full_name=None, password=None):
    existing = conn.execute(
        "SELECT id, email FROM users WHERE role = 'admin' AND is_active = TRUE LIMIT 1"
    ).fetchone()
    if existing:
        print(f"Admin already exists: {existing['email']}. Skipping admin creation.")
        return

    if not email:
        email = input("Admin email: ").strip().lower()
    if not full_name:
        full_name = input("Admin full name (optional): ").strip() or None
    if not password:
        password = getpass.getpass("Admin password (leave empty to generate): ") or generate_temp_password(14)
        print(f"Admin password: {password}")

    conn.execute(
        """INSERT INTO users (email, full_name, password_hash, role, must_change_password)
           VALUES (%s, %s, %s, 'admin', FALSE)""",
        (email.lower(), full_name, hash_password(password))
    )
    print(f"Created admin user: {email}")


def main():
    parser = argparse.ArgumentParser(description="Initialize the Freezer database.")
    parser.add_argument('--admin-email', help="Pre-set admin email (skips prompt).")
    parser.add_argument('--admin-name', help="Pre-set admin full name.")
    parser.add_argument('--admin-password', help="Pre-set admin password (skips prompt).")
    parser.add_argument('--skip-admin', action='store_true', help="Don't create an admin user.")
    args = parser.parse_args()

    if not config.DATABASE_URL:
        sys.exit("DATABASE_URL is not set. Export it before running this script.")

    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        conn.autocommit = False
        _apply_schema(conn)
        _seed_species(conn)
        _seed_freezer_structure(conn)
        if not args.skip_admin:
            _create_admin(conn, args.admin_email, args.admin_name, args.admin_password)
        conn.commit()

    print("Done.")


if __name__ == '__main__':
    main()
