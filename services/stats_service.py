"""Statistics computation for the freezer dashboard."""


def get_raptor_stats(db):
    stats = {}

    stats['total_samples'] = db.execute(
        "SELECT COUNT(*) FROM raptor_tubes"
    ).fetchone()[0]

    rows = db.execute("""
        SELECT s.common_name AS species, s.banding_code AS code, COUNT(*) AS count
        FROM raptor_tubes rt
        JOIN species s ON rt.species_id = s.id
        GROUP BY s.id
        ORDER BY count DESC
    """).fetchall()
    stats['species_breakdown'] = [dict(r) for r in rows]

    rows = db.execute("""
        SELECT strftime('%Y-%m', collection_date) AS month, COUNT(*) AS count
        FROM raptor_tubes
        GROUP BY month
        ORDER BY month
    """).fetchall()
    stats['monthly_counts'] = [dict(r) for r in rows]

    rows = db.execute("""
        SELECT age, COUNT(*) AS count
        FROM raptor_tubes
        WHERE age IS NOT NULL AND age != ''
        GROUP BY age
        ORDER BY count DESC
    """).fetchall()
    stats['age_distribution'] = [dict(r) for r in rows]

    rows = db.execute("""
        SELECT sex, COUNT(*) AS count
        FROM raptor_tubes
        WHERE sex IS NOT NULL AND sex != ''
        GROUP BY sex
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

    raptor_count = db.execute("SELECT COUNT(*) FROM raptor_tubes").fetchone()[0]
    research_count = db.execute("SELECT COUNT(*) FROM research_tubes").fetchone()[0]
    stats['total_stored'] = raptor_count + research_count
    stats['raptor_count'] = raptor_count
    stats['research_count'] = research_count

    if stats['total_capacity'] > 0:
        stats['percent_full'] = round(stats['total_stored'] / stats['total_capacity'] * 100, 1)
    else:
        stats['percent_full'] = 0

    return stats
