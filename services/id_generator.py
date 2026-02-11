"""Raptor tube ID auto-generation.

Format: [4-letter banding code][2-digit year][3-digit sequence]
Example: RTHA26001 (first Red-tailed Hawk of 2026)

The sequence is per-species per-year, so each species starts at 001
for each new year.
"""

import sqlite3
from datetime import datetime


def generate_raptor_tube_id(db, banding_code, species_id, collection_date=None):
    """Generate a unique raptor tube ID atomically.

    Args:
        db: sqlite3 connection (with row_factory set)
        banding_code: 4-letter AOU/AOS alpha code (e.g., 'RTHA')
        species_id: species table primary key
        collection_date: ISO date string (YYYY-MM-DD); defaults to today

    Returns:
        Generated tube ID string (e.g., 'RTHA26001')
    """
    if collection_date:
        year = int(collection_date[:4])
    else:
        year = datetime.now().year

    year_suffix = str(year)[-2:]

    # Atomic read-and-increment within the existing transaction
    row = db.execute(
        "SELECT next_seq FROM raptor_id_sequence WHERE species_id = ? AND year = ?",
        (species_id, year)
    ).fetchone()

    if row is None:
        seq = 1
        db.execute(
            "INSERT INTO raptor_id_sequence (species_id, year, next_seq) VALUES (?, ?, ?)",
            (species_id, year, 2)
        )
    else:
        seq = row[0] if isinstance(row, tuple) else row['next_seq']
        db.execute(
            "UPDATE raptor_id_sequence SET next_seq = ? WHERE species_id = ? AND year = ?",
            (seq + 1, species_id, year)
        )

    return f"{banding_code.upper()}{year_suffix}{seq:03d}"
