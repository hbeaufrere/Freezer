-- ============================================================
-- When a whole box went into the freezer.
--
-- A bulk box records its contents as one line — type, count, study — with
-- no tube rows to carry a date. The box needs one of its own, so a date
-- range on the research filter can find it and the export can say when it
-- was stored. One date per box: the box was closed once.
-- ============================================================

alter table boxes add column if not exists bulk_date date;

comment on column boxes.bulk_date is
    'Whole-box entries only: the date the box was stored. Null for grid and plain boxes.';
