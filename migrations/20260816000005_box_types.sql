-- ============================================================
-- Boxes that hold samples without giving each one a position.
--
-- The 10x10 cryobox is the right model for tubes in a rack, and the wrong one
-- for a handful of whirl-paks of tissue dropped into a box together. Those have
-- no coordinates: asking someone to invent "C7" for a bag records a fiction and
-- makes the grid lie about where things are.
--
-- So a box now has a type. 'grid' keeps the addressed wells; 'plain' is a box
-- whose contents are simply a list. Existing boxes are grid, which is what they
-- have always been.
--
-- Only research tubes lose their NOT NULL. Raptor samples are always positioned
-- —  the whole point of the biobank layout is finding one bird's plasma — and
-- leaving that constraint in place means the database, not just the app, keeps
-- that true.
-- ============================================================

alter table boxes
    add column if not exists box_type text not null default 'grid';

alter table boxes drop constraint if exists boxes_box_type_valid;
alter table boxes add constraint boxes_box_type_valid
    check (box_type in ('grid', 'plain'));

comment on column boxes.box_type is
    'grid = addressed wells (row_pos/col_pos required); '
    'plain = an unordered list of samples, positions null.';

alter table research_tubes alter column row_pos drop not null;
alter table research_tubes alter column col_pos drop not null;

-- The unique (box_id, row_pos, col_pos) constraint still does its job: two
-- tubes cannot share a well in a grid box. Postgres treats nulls as distinct,
-- so any number of positionless samples can sit in the same plain box, which
-- is exactly the behaviour wanted here.

create index if not exists idx_boxes_type on boxes (box_type);
