-- ============================================================
-- Every rack has eight drawers, not seven.
--
-- The freezer was seeded with seven drawers per rack; the racks have eight.
-- This adds D8 to every rack and its four boxes, named the same way as the
-- rest (U1-D8, U1-D8-B1 ...), inheriting the shelf's section. The seed file
-- is corrected too, so a database built fresh matches one that was upgraded.
--
-- Idempotent: a rack that already has a D8 is left alone.
-- ============================================================

insert into drawers (rack_id, position, label)
select r.id,
       8,
       format('%s%s-D8', sh.prefix, r.position)
from racks r
join (
    select id, case position when 1 then 'U' when 2 then 'M' else 'L' end as prefix
    from shelves
) sh on sh.id = r.shelf_id
on conflict (rack_id, position) do nothing;

insert into boxes (drawer_id, position, label, grid_rows, grid_cols, section)
select d.id,
       pos.n,
       format('%s%s-D%s-B%s', sh.prefix, r.position, d.position, pos.n),
       10,
       10,
       sh.section
from drawers d
join racks r on r.id = d.rack_id
join (
    select id, section, case position when 1 then 'U' when 2 then 'M' else 'L' end as prefix
    from shelves
) sh on sh.id = r.shelf_id
cross join generate_series(1, 4) as pos(n)
where d.position = 8
on conflict (drawer_id, position) do nothing;
