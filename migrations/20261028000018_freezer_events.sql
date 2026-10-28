-- ============================================================
-- Things that happened to the whole freezer, and which samples were there.
--
-- A freezer failure, a power cut, a door left open: one short note, dated,
-- that belongs on every sample that was inside at the time and on none of
-- the samples filed afterwards. So an event is linked to the tubes and
-- whole-box entries present when it is recorded, and the link travels with
-- the tube wherever it is moved. A tube added next week has no link, and
-- that is the point.
-- ============================================================

create table if not exists freezer_events (
    id           integer primary key generated always as identity,
    occurred_at  timestamptz not null,
    note         text not null
                 constraint freezer_events_note_short check (length(note) between 1 and 120),
    recorded_by  text,
    created_at   timestamptz not null default now()
);

comment on table freezer_events is
    'Whole-freezer events (failures, door left open). Linked to every tube and whole-box entry present at the time.';

create table if not exists raptor_tube_events (
    tube_id  integer not null references raptor_tubes (id) on delete cascade,
    event_id integer not null references freezer_events (id) on delete cascade,
    primary key (tube_id, event_id)
);

create table if not exists research_tube_events (
    tube_id  integer not null references research_tubes (id) on delete cascade,
    event_id integer not null references freezer_events (id) on delete cascade,
    primary key (tube_id, event_id)
);

-- Whole-box entries have no tube rows, so the link hangs off the box slot
-- and follows the entry when it is moved or is dropped when it is cleared.
create table if not exists box_events (
    box_id   integer not null references boxes (id) on delete cascade,
    event_id integer not null references freezer_events (id) on delete cascade,
    primary key (box_id, event_id)
);

create index if not exists idx_raptor_tube_events_event on raptor_tube_events (event_id);
create index if not exists idx_research_tube_events_event on research_tube_events (event_id);
create index if not exists idx_box_events_event on box_events (event_id);
