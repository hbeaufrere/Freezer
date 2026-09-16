-- ============================================================
-- Free-text notes on racks, matching the ones drawers already have.
--
-- racks.label is the positional name (Rack M1) and stays fixed, and
-- racks.designation is structural: on the raptor shelf it lists the species
-- codes a rack holds and drives which species the form offers, so it is not
-- a thing to type over. This is the line the lab actually writes on the
-- rack — a study, a project, a person — and it is free to say anything.
-- ============================================================

alter table racks add column if not exists note text;

comment on column racks.note is
    'Free-text label written by the lab: study, project or owner. '
    'Distinct from designation, which is structural and drives the species list.';
