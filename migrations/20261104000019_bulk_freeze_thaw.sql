-- ============================================================
-- A freeze-thaw count for a whole-box entry.
--
-- An itemised box counts thaws per tube. A whole-box entry has no tube
-- rows, so until now it could not count at all: the box came out, went
-- back, and nothing said so. One count on the box, kept while the entry
-- is a whole-box entry and reset when it is cleared.
-- ============================================================

alter table boxes add column if not exists bulk_freeze_thaw integer not null default 0;

comment on column boxes.bulk_freeze_thaw is
    'Whole-box entries only: freeze-thaw cycles for the box as a whole. 0 for gridded and plain boxes.';
