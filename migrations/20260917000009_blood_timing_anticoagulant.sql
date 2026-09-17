-- ============================================================
-- What a blood sample is, beyond "plasma": when in the bird's stay it was
-- drawn, and what tube it was drawn into.
--
-- Timing (Intake / Under care / Pre-release) is the variable a rehab
-- biobank exists to compare across, and it is per tube, not per bird: one
-- bird can yield intake plasma and pre-release plasma weeks apart. The
-- anticoagulant (Heparin / EDTA / Other) decides which assays a plasma
-- sample is good for, and is the first thing a collaborator asks.
--
-- Both are free text, like sample_type, with the allowed values enforced by
-- the app; both are null for anything that is not blood. Existing rows are
-- left null rather than backfilled with a guess — the form will ask for the
-- timing the next time each one is edited.
-- ============================================================

alter table raptor_tubes add column if not exists blood_timing  text;
alter table raptor_tubes add column if not exists anticoagulant text;

comment on column raptor_tubes.blood_timing is
    'Plasma and packed RBCs only: Intake, Under care or Pre-release. Required by the app for blood.';
comment on column raptor_tubes.anticoagulant is
    'Plasma and packed RBCs only: Heparin, EDTA or Other (described in notes).';

create index if not exists idx_raptor_tubes_blood_timing on raptor_tubes (blood_timing);
