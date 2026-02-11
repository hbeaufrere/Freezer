"""Statistics computation for the freezer dashboard."""

# SQL expression to extract base tube ID (strips "-N" suffix for multi-tube samples).
# e.g. "RTHA26001-1" → "RTHA26001", "RTHA26001" → "RTHA26001"
_BASE_ID = """CASE WHEN INSTR(rt.tube_id, '-') > 0
              THEN SUBSTR(rt.tube_id, 1, INSTR(rt.tube_id, '-') - 1)
              ELSE rt.tube_id END"""


def get_raptor_stats(db):
    stats = {}

    # Count unique samples (tubes from the same bird count as one)
    stats['total_samples'] = db.execute(
        f"SELECT COUNT(DISTINCT {_BASE_ID}) FROM raptor_tubes rt"
    ).fetchone()[0]

    rows = db.execute(f"""
        SELECT s.common_name AS species, s.banding_code AS code,
               COUNT(DISTINCT {_BASE_ID}) AS count
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        GROUP BY s.id
        ORDER BY count DESC
    """).fetchall()
    stats['species_breakdown'] = [dict(r) for r in rows]

    rows = db.execute(f"""
        SELECT strftime('%Y-%m', rt.collection_date) AS month,
               COUNT(DISTINCT {_BASE_ID}) AS count
        FROM raptor_tubes rt
        GROUP BY month
        ORDER BY month
    """).fetchall()
    stats['monthly_counts'] = [dict(r) for r in rows]

    rows = db.execute(f"""
        SELECT rt.age, COUNT(DISTINCT {_BASE_ID}) AS count
        FROM raptor_tubes rt
        WHERE rt.age IS NOT NULL AND rt.age != ''
        GROUP BY rt.age
        ORDER BY count DESC
    """).fetchall()
    stats['age_distribution'] = [dict(r) for r in rows]

    rows = db.execute(f"""
        SELECT rt.sex, COUNT(DISTINCT {_BASE_ID}) AS count
        FROM raptor_tubes rt
        WHERE rt.sex IS NOT NULL AND rt.sex != ''
        GROUP BY rt.sex
    """).fetchall()
    stats['sex_distribution'] = [dict(r) for r in rows]

    val = db.execute(
        "SELECT ROUND(AVG(freeze_thaw_cycles), 1) FROM raptor_tubes"
    ).fetchone()[0]
    stats['avg_freeze_thaw_cycles'] = val if val is not None else 0

    return stats


def get_research_stats(db):
    stats = {}

    stats['total_samples'] = db.execute(
        "SELECT COUNT(*) FROM research_tubes"
    ).fetchone()[0]

    stats['boxes_with_samples'] = db.execute(
        "SELECT COUNT(DISTINCT box_id) FROM research_tubes"
    ).fetchone()[0]

    # Total research boxes available
    stats['total_boxes'] = db.execute(
        "SELECT COUNT(*) FROM boxes WHERE section = 'research'"
    ).fetchone()[0]

    # Occupancy per rack
    rows = db.execute("""
        SELECT r.label AS rack, COUNT(rt.id) AS count
        FROM racks r
        JOIN drawers d ON d.rack_id = r.id
        JOIN boxes b ON b.drawer_id = d.id
        LEFT JOIN research_tubes rt ON rt.box_id = b.id
        WHERE b.section = 'research'
        GROUP BY r.id
        ORDER BY r.label
    """).fetchall()
    stats['occupancy_by_rack'] = [dict(r) for r in rows]

    return stats


def get_freezer_stats(db):
    stats = {}

    # Total capacity (all boxes * grid size)
    row = db.execute(
        "SELECT COUNT(*) AS box_count, SUM(grid_rows * grid_cols) AS total_capacity FROM boxes"
    ).fetchone()
    stats['total_boxes'] = row[0]
    stats['total_capacity'] = row[1] or 0

    raptor_count = db.execute(
        f"SELECT COUNT(DISTINCT {_BASE_ID}) FROM raptor_tubes rt"
    ).fetchone()[0]
    research_count = db.execute("SELECT COUNT(*) FROM research_tubes").fetchone()[0]
    stats['total_stored'] = raptor_count + research_count
    stats['raptor_count'] = raptor_count
    stats['research_count'] = research_count

    if stats['total_capacity'] > 0:
        stats['percent_full'] = round(stats['total_stored'] / stats['total_capacity'] * 100, 1)
    else:
        stats['percent_full'] = 0

    return stats
