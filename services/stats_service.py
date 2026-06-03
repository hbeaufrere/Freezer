"""Statistics computation for the freezer dashboard."""

# SQL expression to extract base tube ID (strips "-N" suffix for multi-tube samples).
# e.g. "RTHA26001-1" -> "RTHA26001", "RTHA26001" -> "RTHA26001"
_BASE_ID = """CASE WHEN POSITION('-' IN rt.tube_id) > 0
              THEN SUBSTRING(rt.tube_id FROM 1 FOR POSITION('-' IN rt.tube_id) - 1)
              ELSE rt.tube_id END"""


def get_raptor_stats(db):
    stats = {}

    stats['total_samples'] = db.execute(
        f"SELECT COUNT(DISTINCT {_BASE_ID}) AS c FROM raptor_tubes rt"
    ).fetchone()['c']

    rows = db.execute(f"""
        SELECT s.common_name AS species, s.banding_code AS code,
               COUNT(DISTINCT {_BASE_ID}) AS count
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        GROUP BY s.id, s.common_name, s.banding_code
        ORDER BY count DESC
    """).fetchall()
    stats['species_breakdown'] = [dict(r) for r in rows]

    rows = db.execute(f"""
        SELECT TO_CHAR(rt.collection_date, 'YYYY-MM') AS month,
               COUNT(DISTINCT {_BASE_ID}) AS count
        FROM raptor_tubes rt
        GROUP BY TO_CHAR(rt.collection_date, 'YYYY-MM')
        ORDER BY month
    """).fetchall()
    stats['monthly_counts'] = [dict(r) for r in rows]

    rows = db.execute(f"""
        SELECT rt.age, COUNT(DISTINCT {_BASE_ID}) AS count
        FROM raptor_tubes rt
        WHERE rt.age IS NOT NULL AND rt.age <> ''
        GROUP BY rt.age
        ORDER BY count DESC
    """).fetchall()
    stats['age_distribution'] = [dict(r) for r in rows]

    rows = db.execute(f"""
        SELECT rt.sex, COUNT(DISTINCT {_BASE_ID}) AS count
        FROM raptor_tubes rt
        WHERE rt.sex IS NOT NULL AND rt.sex <> ''
        GROUP BY rt.sex
    """).fetchall()
    stats['sex_distribution'] = [dict(r) for r in rows]

    val = db.execute(
        "SELECT ROUND(AVG(freeze_thaw_cycles)::numeric, 1) AS v FROM raptor_tubes"
    ).fetchone()['v']
    stats['avg_freeze_thaw_cycles'] = float(val) if val is not None else 0

    return stats


def get_research_stats(db):
    stats = {}

    stats['total_samples'] = db.execute(
        "SELECT COUNT(*) AS c FROM research_tubes"
    ).fetchone()['c']

    stats['boxes_with_samples'] = db.execute(
        "SELECT COUNT(DISTINCT box_id) AS c FROM research_tubes"
    ).fetchone()['c']

    stats['total_boxes'] = db.execute(
        "SELECT COUNT(*) AS c FROM boxes WHERE section = 'research'"
    ).fetchone()['c']

    rows = db.execute("""
        SELECT r.label AS rack, COUNT(rt.id) AS count
        FROM racks r
        JOIN drawers d ON d.rack_id = r.id
        JOIN boxes b ON b.drawer_id = d.id
        LEFT JOIN research_tubes rt ON rt.box_id = b.id
        WHERE b.section = 'research'
        GROUP BY r.id, r.label
        ORDER BY r.label
    """).fetchall()
    stats['occupancy_by_rack'] = [dict(r) for r in rows]

    return stats


def get_freezer_stats(db):
    row = db.execute(f"""
        SELECT
            (SELECT COUNT(*) FROM boxes) AS total_boxes,
            (SELECT COALESCE(SUM(grid_rows * grid_cols), 0) FROM boxes) AS total_capacity,
            (SELECT COUNT(DISTINCT {_BASE_ID}) FROM raptor_tubes rt) AS raptor_count,
            (SELECT COUNT(*) FROM research_tubes) AS research_count
    """).fetchone()

    stats = {
        'total_boxes': row['total_boxes'],
        'total_capacity': row['total_capacity'],
        'raptor_count': row['raptor_count'],
        'research_count': row['research_count'],
        'total_stored': row['raptor_count'] + row['research_count'],
    }
    stats['percent_full'] = (
        round(stats['total_stored'] / stats['total_capacity'] * 100, 1)
        if stats['total_capacity'] > 0 else 0
    )
    return stats
