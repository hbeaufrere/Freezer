-- ============================================================
-- A box described as a whole: what is in it, how many, and for which study.
--
-- Some research boxes hold dozens of tubes whose labels cannot be read
-- without thawing the box. Filing them one by one is not possible, and a
-- box that stays empty in the record because its contents cannot be
-- itemised is worse than one summarised honestly. So a box can now be
-- "bulk": one entry for the whole box, no individual tubes.
--
-- The count feeds occupancy and the section totals, so the freezer figures
-- stay true. The fields stay on the row when a box is switched back to a
-- grid or a plain box — they are simply not counted — so the change is
-- reversible and nothing typed is lost.
-- ============================================================

alter table boxes drop constraint if exists boxes_box_type_valid;
alter table boxes add constraint boxes_box_type_valid
    check (box_type in ('grid', 'plain', 'bulk'));

alter table boxes add column if not exists bulk_sample_type text;
alter table boxes add column if not exists bulk_tube_count  integer;
alter table boxes add column if not exists bulk_study       text;

alter table boxes drop constraint if exists boxes_bulk_tube_count_valid;
alter table boxes add constraint boxes_bulk_tube_count_valid
    check (bulk_tube_count is null or bulk_tube_count >= 0);

comment on column boxes.box_type is
    'grid = addressed wells; plain = an unordered list of samples; '
    'bulk = one entry for the whole box, counted but not itemised.';
comment on column boxes.bulk_tube_count is
    'Bulk boxes only: how many tubes the box holds. Counts towards occupancy.';
