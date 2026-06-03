"""Raptor tube ID auto-generation.

Format: [4-letter banding code][2-digit year][3-digit sequence]
Example: RTHA26001 (first Red-tailed Hawk of 2026)

The sequence is per-species per-year, so each species starts at 001 each year.
Atomic: the calling route owns the transaction.
"""

from datetime import datetime


def generate_raptor_tube_id(db, banding_code, species_id, collection_date=None):
    """Generate the next unique raptor tube ID within the caller's transaction."""
    if collection_date:
        year = int(str(collection_date)[:4])
    else:
        year = datetime.now().year

    year_suffix = str(year)[-2:]

    # Lock the sequence row (if it exists) so concurrent inserts can't race.
    row = db.execute(
        "SELECT next_seq FROM raptor_id_sequence WHERE species_id = %s AND year = %s FOR UPDATE",
        (species_id, year)
    ).fetchone()

    if row is None:
        seq = 1
        db.execute(
            "INSERT INTO raptor_id_sequence (species_id, year, next_seq) VALUES (%s, %s, %s)",
            (species_id, year, 2)
        )
    else:
        seq = row['next_seq']
        db.execute(
            "UPDATE raptor_id_sequence SET next_seq = %s WHERE species_id = %s AND year = %s",
            (seq + 1, species_id, year)
        )

    return f"{banding_code.upper()}{year_suffix}{seq:03d}"
