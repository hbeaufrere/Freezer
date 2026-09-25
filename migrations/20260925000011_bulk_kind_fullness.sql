-- ============================================================
-- What a whole box is full *of*, and — when that is not tubes — how full.
--
-- A whole box of tubes colours itself: 48 tubes in a 100-well box is 48%.
-- A whole box of bags, blocks or swabs has no such arithmetic: twelve
-- whirl-paks might pack a box or rattle around in it. So the box says which
-- it holds, and for anything other than tubes the fullness is stated by the
-- person who closed the lid. The count is still recorded either way — it is
-- the number of samples — it just stops standing in for space.
-- ============================================================

alter table boxes add column if not exists bulk_kind     text    not null default 'tubes';
alter table boxes add column if not exists bulk_fullness integer;

alter table boxes drop constraint if exists boxes_bulk_kind_valid;
alter table boxes add constraint boxes_bulk_kind_valid
    check (bulk_kind in ('tubes', 'other'));

alter table boxes drop constraint if exists boxes_bulk_fullness_valid;
alter table boxes add constraint boxes_bulk_fullness_valid
    check (bulk_fullness is null or bulk_fullness between 0 and 100);

comment on column boxes.bulk_kind is
    'Whole boxes only: tubes (fullness is count over capacity) or other '
    '(fullness is stated in bulk_fullness).';
comment on column boxes.bulk_fullness is
    'Whole boxes of kind "other" only: how full, 0-100, as judged by the person filling it.';
