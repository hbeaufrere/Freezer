-- ============================================================
-- What happened in the freezer, beyond retrievals.
--
-- The retrieval log answers "who took this out". Nothing answered "what
-- came in this week", "who moved rack M1", or "when did this box become a
-- whole-box entry". This table does: one row per event, with a snapshot of
-- the tube and place as they were, so the row still reads after the tube
-- is renamed, moved or gone.
--
-- Retrievals stay in their own table — they carry fields of their own —
-- and the activity feed reads both.
-- ============================================================

create table if not exists activity (
    id             integer primary key generated always as identity,
    at             timestamptz not null default now(),
    section        text not null,
    kind           text not null,
    tube_label     text,
    box_label      text,
    position_label text,
    species_name   text,
    detail         text,
    actor          text
);

comment on table activity is
    'One row per change to the freezer: tubes added, edited, removed, moved, thawed; boxes retyped; drop-offs. Snapshots, not references.';

create index if not exists idx_activity_at on activity (at desc);
create index if not exists idx_activity_section_at on activity (section, at desc);
