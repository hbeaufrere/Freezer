-- ============================================================
-- Record what tissue each raptor tube holds.
--
-- The biobank started as plasma only, so existing rows are backfilled as
-- 'Plasma'. Left as free text rather than an enum or check constraint: the
-- form offers Plasma / Liver / Other, but a new tissue type should not need
-- a schema migration to start recording. This matches how age and sex are
-- already handled.
-- ============================================================

alter table raptor_tubes
    add column if not exists sample_type text not null default 'Plasma';

comment on column raptor_tubes.sample_type is
    'Tissue held by this tube. The form offers Plasma, Liver and Other; '
    'anything else is described in notes.';

create index if not exists idx_raptor_tubes_sample_type on raptor_tubes (sample_type);
