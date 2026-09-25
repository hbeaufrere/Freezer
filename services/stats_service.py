"""Statistics computation for the freezer dashboard."""

# Tubes split from one bird share a base ID with a -N suffix (RTHA26001-2).
# Counting distinct base IDs counts birds, not tubes.
_BASE_ID = "split_part(rt.tube_id, '-', 1)"


def get_raptor_stats(db):
    stats = {}

    stats['total_samples'] = db.execute(
        f'select count(distinct {_BASE_ID}) as n from raptor_tubes rt'
    ).fetchone()['n']

    stats['total_tubes'] = db.execute(
        'select count(*) as n from raptor_tubes'
    ).fetchone()['n']

    stats['species_breakdown'] = [dict(r) for r in db.execute(
        f"""select s.common_name as species, s.banding_code as code,
                   count(distinct {_BASE_ID}) as count
            from raptor_tubes rt
            join species s on rt.species_id = s.id
            group by s.id, s.common_name, s.banding_code
            order by count desc, s.common_name"""
    ).fetchall()]

    stats['monthly_counts'] = [dict(r) for r in db.execute(
        f"""select to_char(rt.collection_date, 'YYYY-MM') as month,
                   count(distinct {_BASE_ID}) as count
            from raptor_tubes rt
            group by month
            order by month"""
    ).fetchall()]

    stats['age_distribution'] = [dict(r) for r in db.execute(
        f"""select rt.age, count(distinct {_BASE_ID}) as count
            from raptor_tubes rt
            where rt.age is not null and rt.age <> ''
            group by rt.age
            order by count desc"""
    ).fetchall()]

    stats['sex_distribution'] = [dict(r) for r in db.execute(
        f"""select rt.sex, count(distinct {_BASE_ID}) as count
            from raptor_tubes rt
            where rt.sex is not null and rt.sex <> ''
            group by rt.sex
            order by count desc"""
    ).fetchall()]

    # Cast to float8 so the JSON encoder sees a number rather than a Decimal.
    stats['avg_freeze_thaw_cycles'] = db.execute(
        """select coalesce(round(avg(freeze_thaw_cycles), 1), 0)::float8 as avg
           from raptor_tubes"""
    ).fetchone()['avg']

    return stats


def get_research_stats(db):
    stats = {}

    # Bulk boxes hold tubes that were never itemised; they still count.
    stats['total_samples'] = db.execute(
        """select (select count(*) from research_tubes)
                + (select coalesce(sum(bulk_tube_count), 0) from boxes where box_type = 'bulk')
                as n"""
    ).fetchone()['n']

    stats['boxes_with_samples'] = db.execute(
        """select count(*) as n from boxes b
           where exists (select 1 from research_tubes rt where rt.box_id = b.id)
              or (b.box_type = 'bulk'
                  and (coalesce(b.bulk_tube_count, 0) > 0 or coalesce(b.bulk_fullness, 0) > 0))"""
    ).fetchone()['n']

    stats['total_boxes'] = db.execute(
        "select count(*) as n from boxes where section = 'research'"
    ).fetchone()['n']

    stats['avg_freeze_thaw_cycles'] = db.execute(
        """select coalesce(round(avg(freeze_thaw_cycles), 1), 0)::float8 as avg
           from research_tubes"""
    ).fetchone()['avg']

    return stats


def get_freezer_stats(db):
    stats = {}

    totals = db.execute(
        """select count(*) as box_count,
                  coalesce(sum(grid_rows * grid_cols), 0) as total_capacity
           from boxes"""
    ).fetchone()
    stats['total_boxes'] = totals['box_count']
    stats['total_capacity'] = totals['total_capacity']

    stats['raptor_count'] = db.execute(
        f'select count(distinct {_BASE_ID}) as n from raptor_tubes rt'
    ).fetchone()['n']

    # Tubes per sample type. Birds are the headline; this is what the birds
    # yielded, and "do we have any liver" is a question asked of the card
    # itself rather than of the statistics page.
    stats['raptor_sample_types'] = [
        dict(r) for r in db.execute(
            """select coalesce(nullif(sample_type, ''), 'Plasma') as sample_type,
                      count(*) as count
               from raptor_tubes
               group by 1
               order by count desc, sample_type"""
        ).fetchall()
    ]
    stats['research_count'] = db.execute(
        """select (select count(*) from research_tubes)
                + (select coalesce(sum(bulk_tube_count), 0) from boxes where box_type = 'bulk')
                as n"""
    ).fetchone()['n']

    # Physical occupancy is one slot per tube, so multi-tube samples count
    # individually here even though the biobank totals count them as one bird.
    # Space, not items: a whole box of bags counts by how full it is said to
    # be, so the percent-of-capacity figure means what it says.
    stats['tubes_stored'] = db.execute(
        """select (select count(*) from raptor_tubes)
                + (select count(*) from research_tubes)
                + (select coalesce(sum(
                        case when bulk_kind = 'other'
                             then round(coalesce(bulk_fullness, 0) * grid_rows * grid_cols / 100.0)::int
                             else least(coalesce(bulk_tube_count, 0), grid_rows * grid_cols) end), 0)
                   from boxes where box_type = 'bulk')::bigint
                as n"""
    ).fetchone()['n']
    stats['total_stored'] = stats['raptor_count'] + stats['research_count']

    capacity = stats['total_capacity']
    stats['percent_full'] = round(stats['tubes_stored'] / capacity * 100, 1) if capacity else 0

    return stats
