-- ============================================================
-- Retrieval log, and free-text notes on drawers.
-- ============================================================

-- ------------------------------------------------------------
-- Drawer notes
--
-- drawers.label is the positional name (M1-D3) and stays fixed. This is the
-- line the lab actually writes on the drawer: an experiment, a species, a
-- project code.
-- ------------------------------------------------------------

alter table drawers add column if not exists note text;

comment on column drawers.note is
    'Free-text label written by the lab: experiment, species or project.';

-- ------------------------------------------------------------
-- Retrieval log
--
-- Who took what out, when, and what for. Entries are deliberately
-- denormalised: tube_label and box_label are snapshots taken at the moment of
-- retrieval, so the log still reads correctly after a tube is consumed and
-- its row deleted. The foreign keys are nullable and ON DELETE SET NULL for
-- the same reason — losing the tube must never lose the history.
-- ------------------------------------------------------------

create table if not exists retrievals (
    id                integer primary key generated always as identity,
    section           text not null
                      constraint retrievals_section_valid check (section in ('raptor', 'research')),

    raptor_tube_id    integer references raptor_tubes (id) on delete set null,
    research_tube_id  integer references research_tubes (id) on delete set null,

    -- Snapshots, so the entry survives the tube.
    tube_label        text not null,
    box_label         text,
    position_label    text,
    species_name      text,

    retrieved_at      timestamptz not null default now(),
    retrieved_by      text not null,
    purpose           text,
    notes             text,
    -- Was the tube used up, or put back in the freezer?
    consumed          boolean not null default false,

    created_at        timestamptz not null default now(),

    constraint retrievals_one_tube check (
        (raptor_tube_id is not null and research_tube_id is null)
        or (raptor_tube_id is null and research_tube_id is not null)
        or (raptor_tube_id is null and research_tube_id is null)
    )
);

create index if not exists idx_retrievals_at       on retrievals (retrieved_at desc);
create index if not exists idx_retrievals_by       on retrievals (retrieved_by);
create index if not exists idx_retrievals_section  on retrievals (section);
create index if not exists idx_retrievals_raptor   on retrievals (raptor_tube_id);
create index if not exists idx_retrievals_research on retrievals (research_tube_id);
