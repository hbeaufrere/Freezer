-- ============================================================
-- A fourth blood timing: Resident/captive.
--
-- Not every bird sampled is passing through rehabilitation. Permanent
-- residents and other captive birds have no intake or release, so none of
-- the three existing timings is true of them. The allowed values are still
-- enforced by the app; this only keeps the column's comment honest.
-- ============================================================

comment on column raptor_tubes.blood_timing is
    'Plasma and packed RBCs only: Intake, Under care, Pre-release or Resident/captive. Required by the app for blood.';
