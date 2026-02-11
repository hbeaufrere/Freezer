#!/usr/bin/env python3
"""Migration: Update species taxonomy (AOS 65th/66th Supplements), add rack designations,
update box grids to 10x10, and add freeze-thaw tracking to research tubes.

Changes:
  - Barn Owl → American Barn Owl (Tyto furcata), BANO → ABOW
  - Northern Goshawk → American Goshawk (Astur atricapillus), NOGO → AGOS
  - Cooper's Hawk: Accipiter cooperii → Astur cooperii (code stays COHA)
  - Add 'designation' column to racks table
  - Set species-group designations on upper-shelf (raptor) racks
  - Update all 9x9 box grids to 10x10 (rows A-H,J-K / cols 1-10)
  - Add 'freeze_thaw_cycles' column to research_tubes table

Safe to run multiple times (idempotent).
"""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'db', 'freezer.db')


def migrate():
    if not os.path.exists(DB_PATH):
        print("No database found. Run init_db.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")

    # --- 1. Add designation column to racks if missing ---
    cols = [row[1] for row in conn.execute("PRAGMA table_info(racks)").fetchall()]
    if 'designation' not in cols:
        conn.execute("ALTER TABLE racks ADD COLUMN designation TEXT")
        print("Added 'designation' column to racks table.")
    else:
        print("'designation' column already exists.")

    # --- 2. Update species taxonomy ---
    taxonomy_updates = [
        # (old_banding_code, new_common_name, new_scientific_name, new_banding_code)
        ('BANO', 'American Barn Owl', 'Tyto furcata', 'ABOW'),
        ('NOGO', 'American Goshawk', 'Astur atricapillus', 'AGOS'),
    ]

    # Scientific name only updates (banding code stays the same)
    sci_name_updates = [
        ('COHA', 'Astur cooperii'),
    ]

    for old_code, new_name, new_sci, new_code in taxonomy_updates:
        row = conn.execute(
            "SELECT id FROM species WHERE banding_code = ?", (old_code,)
        ).fetchone()
        if row:
            # Check new code doesn't already exist (from a previous partial migration)
            existing = conn.execute(
                "SELECT id FROM species WHERE banding_code = ?", (new_code,)
            ).fetchone()
            if existing and existing[0] != row[0]:
                print(f"WARNING: {new_code} already exists as a different species. Skipping {old_code} → {new_code}.")
                continue
            conn.execute(
                "UPDATE species SET common_name = ?, scientific_name = ?, banding_code = ? WHERE id = ?",
                (new_name, new_sci, new_code, row[0])
            )
            print(f"Updated {old_code} → {new_code} ({new_name}, {new_sci})")
        else:
            # Check if already migrated
            already = conn.execute(
                "SELECT id FROM species WHERE banding_code = ?", (new_code,)
            ).fetchone()
            if already:
                print(f"Already up to date: {new_code} ({new_name})")
            else:
                print(f"Species with code {old_code} not found, skipping.")

    for code, new_sci in sci_name_updates:
        row = conn.execute(
            "SELECT id, scientific_name FROM species WHERE banding_code = ?", (code,)
        ).fetchone()
        if row:
            if row[1] != new_sci:
                conn.execute(
                    "UPDATE species SET scientific_name = ? WHERE id = ?",
                    (new_sci, row[0])
                )
                print(f"Updated {code} scientific name: {row[1]} → {new_sci}")
            else:
                print(f"Already up to date: {code} ({new_sci})")
        else:
            print(f"Species with code {code} not found, skipping.")

    # --- 3. Set rack designations on upper shelf (raptor) racks ---
    raptor_rack_designations = {
        1: 'RTHA / RSHA / SWHA',
        2: 'COHA / WTKI',
        3: 'GHOW / ABOW',
        4: 'WESO / Other Owls',
        5: 'AMKE / TUVU',
        6: 'Other Species',
    }

    raptor_shelf = conn.execute(
        "SELECT id FROM shelves WHERE section = 'raptor'"
    ).fetchone()

    if raptor_shelf:
        for rack_pos, designation in raptor_rack_designations.items():
            conn.execute(
                "UPDATE racks SET designation = ? WHERE shelf_id = ? AND position = ?",
                (designation, raptor_shelf[0], rack_pos)
            )
        print("Set species-group designations on raptor racks.")
    else:
        print("No raptor shelf found, skipping rack designations.")

    # --- 4. Add freeze_thaw_cycles to research_tubes if missing ---
    rt_cols = [row[1] for row in conn.execute("PRAGMA table_info(research_tubes)").fetchall()]
    if 'freeze_thaw_cycles' not in rt_cols:
        conn.execute("ALTER TABLE research_tubes ADD COLUMN freeze_thaw_cycles INTEGER NOT NULL DEFAULT 0")
        print("Added 'freeze_thaw_cycles' column to research_tubes table.")
    else:
        print("'freeze_thaw_cycles' column already exists in research_tubes.")

    # --- 5. Update box grids from 9x9 to 10x10 ---
    updated = conn.execute(
        "UPDATE boxes SET grid_rows = 10, grid_cols = 10 WHERE grid_rows = 9 AND grid_cols = 9"
    ).rowcount
    if updated:
        print(f"Updated {updated} boxes from 9x9 to 10x10 grid.")
    else:
        print("All boxes already 10x10 (or no 9x9 boxes found).")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    migrate()
