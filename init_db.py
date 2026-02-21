#!/usr/bin/env python3
"""Initialize the freezer database with schema, species data, and default freezer structure."""

import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'db', 'freezer.db')


def init_database():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")

    # Run schema
    with open(os.path.join(BASE_DIR, 'schema.sql'), 'r') as f:
        conn.executescript(f.read())

    # Run species seed
    with open(os.path.join(BASE_DIR, 'seed_species.sql'), 'r') as f:
        conn.executescript(f.read())

    # Insert default freezer structure if empty
    count = conn.execute("SELECT COUNT(*) FROM shelves").fetchone()[0]
    if count == 0:
        _seed_freezer_structure(conn)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def _seed_freezer_structure(conn):
    """Create the default Eppendorf CryoCube F740hi structure.

    Layout: 3 shelves, 6 racks per shelf, 8 drawers per rack, 4 boxes per drawer.
    Upper shelf is for the raptor biobank, middle and lower are for research.

    Raptor rack designations (upper shelf) group common species together:
      U1 - Buteo Hawks: RTHA, RSHA, SWHA
      U2 - Accipiters & Kites: COHA, WTKI
      U3 - Large Owls: GHOW, ABOW
      U4 - Small Owls: WESO + other owls
      U5 - Falcons & Vultures: AMKE, TUVU
      U6 - Other Species (overflow)
    """
    # Species-group designations for upper-shelf (raptor) racks
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
        conn.execute(
            "INSERT INTO shelves (name, position, section) VALUES (?, ?, ?)",
            (shelf_name, shelf_pos, section)
        )
        shelf_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Shelf position label prefix
        shelf_prefix = {1: 'U', 2: 'M', 3: 'L'}[shelf_pos]

        for rack_pos in range(1, 7):  # 6 racks per shelf
            rack_label = f"Rack {shelf_prefix}{rack_pos}"
            designation = raptor_rack_designations.get(rack_pos) if section == 'raptor' else None
            conn.execute(
                "INSERT INTO racks (shelf_id, position, label, designation) VALUES (?, ?, ?, ?)",
                (shelf_id, rack_pos, rack_label, designation)
            )
            rack_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            for drawer_pos in range(1, 9):  # 8 drawers per rack
                drawer_label = f"{shelf_prefix}{rack_pos}-D{drawer_pos}"
                conn.execute(
                    "INSERT INTO drawers (rack_id, position, label) VALUES (?, ?, ?)",
                    (rack_id, drawer_pos, drawer_label)
                )
                drawer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

                for box_pos in range(1, 5):  # 4 boxes per drawer
                    box_label = f"{shelf_prefix}{rack_pos}-D{drawer_pos}-B{box_pos}"
                    conn.execute(
                        "INSERT INTO boxes (drawer_id, position, label, grid_rows, grid_cols, section) VALUES (?, ?, ?, ?, ?, ?)",
                        (drawer_id, box_pos, box_label, 10, 10, section)
                    )


if __name__ == '__main__':
    init_database()
