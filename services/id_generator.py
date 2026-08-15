"""Raptor tube ID generation.

Format: [4-letter banding code][2-digit year][3-digit sequence]
Example: RTHA26001 — the first Red-tailed Hawk of 2026.

The sequence restarts at 001 for each species each year.
"""


def generate_raptor_tube_id(db, banding_code, species_id, collection_date):
    """Reserve and return the next tube ID for this species and year.

    The counter is claimed with a single upsert, so two people submitting at
    the same moment get consecutive IDs rather than colliding on one. The row
    stays locked until the caller's transaction commits, which means a failed
    insert releases the number instead of burning it.

    Args:
        db: an open connection with a dict row factory
        banding_code: 4-letter BBL alpha code, e.g. 'RTHA'
        species_id: species table primary key
        collection_date: a ``datetime.date``

    Returns:
        The generated tube ID, e.g. 'RTHA26001'.
    """
    year = collection_date.year

    row = db.execute(
        """insert into raptor_id_sequence (species_id, year, next_seq)
           values (%s, %s, 2)
           on conflict (species_id, year)
           do update set next_seq = raptor_id_sequence.next_seq + 1
           returning next_seq""",
        (species_id, year),
    ).fetchone()

    # next_seq is what the *following* tube will use, so this tube gets one less.
    sequence = row['next_seq'] - 1
    return f'{banding_code.upper()}{year % 100:02d}{sequence:03d}'
