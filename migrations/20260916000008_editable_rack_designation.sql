-- ============================================================
-- The rack's species line is the editable name; the note goes.
--
-- 0007 gave racks a separate note, which turned out to be a subtitle under a
-- title that still could not be changed. What was wanted was the title —
-- the designation line ("RTHA / RSHA / SWHA") — editable in place. That is a
-- code change, not a schema one, but it makes the note column dead weight,
-- and a column nothing reads is worse than none: the next person has to
-- work out whether it matters.
-- ============================================================

alter table racks drop column if exists note;

comment on column racks.designation is
    'The rack''s name, editable in place. On the raptor shelf it usually lists '
    'species codes, which the sample form uses to narrow the species list; '
    'free text is fine and simply means "any species".';
