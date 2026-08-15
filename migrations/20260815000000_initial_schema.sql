-- ============================================================
-- Biorepository freezer management — initial schema (PostgreSQL)
--
-- Hierarchy: shelf → rack → drawer → box → tube position
-- Two sections share the same physical structure:
--   'raptor'   — the raptor plasma biobank (auto-generated tube IDs)
--   'research' — CLIPR research samples (free-text sample IDs)
-- ============================================================

-- ------------------------------------------------------------
-- updated_at maintenance
-- ------------------------------------------------------------

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

-- ------------------------------------------------------------
-- Physical structure
-- ------------------------------------------------------------

create table if not exists shelves (
    id       integer primary key generated always as identity,
    name     text    not null unique,
    position integer not null unique,
    section  text    not null default 'research'
             constraint shelves_section_valid check (section in ('raptor', 'research'))
);

comment on column shelves.position is '1 = upper, ascending downwards';

create table if not exists racks (
    id          integer primary key generated always as identity,
    shelf_id    integer not null references shelves (id) on delete cascade,
    position    integer not null,
    label       text,
    -- Species-group label, e.g. 'RTHA / RSHA / SWHA'. Drives which species the
    -- raptor form offers for boxes in this rack.
    designation text,
    unique (shelf_id, position)
);

create table if not exists drawers (
    id       integer primary key generated always as identity,
    rack_id  integer not null references racks (id) on delete cascade,
    position integer not null,
    label    text,
    unique (rack_id, position)
);

create table if not exists boxes (
    id        integer primary key generated always as identity,
    drawer_id integer not null references drawers (id) on delete cascade,
    position  integer not null,
    label     text,
    grid_rows integer not null default 10
              constraint boxes_grid_rows_valid check (grid_rows between 1 and 26),
    grid_cols integer not null default 10
              constraint boxes_grid_cols_valid check (grid_cols between 1 and 26),
    section   text    not null default 'research'
              constraint boxes_section_valid check (section in ('raptor', 'research')),
    unique (drawer_id, position)
);

comment on column boxes.position is '1 = front/superficial, ascending towards the back of the drawer';

-- ------------------------------------------------------------
-- Research section
-- ------------------------------------------------------------

create table if not exists research_tubes (
    id                 integer primary key generated always as identity,
    box_id             integer not null references boxes (id) on delete cascade,
    row_pos            integer not null constraint research_tubes_row_valid check (row_pos >= 1),
    col_pos            integer not null constraint research_tubes_col_valid check (col_pos >= 1),
    sample_id          text,
    description        text,
    date_stored        date,
    freeze_thaw_cycles integer not null default 0
                       constraint research_tubes_ft_valid check (freeze_thaw_cycles >= 0),
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    unique (box_id, row_pos, col_pos)
);

create or replace trigger research_tubes_set_updated_at
    before update on research_tubes
    for each row execute function set_updated_at();

-- ------------------------------------------------------------
-- Raptor biobank
-- ------------------------------------------------------------

create table if not exists species (
    id              integer primary key generated always as identity,
    common_name     text not null,
    scientific_name text not null,
    banding_code    text not null unique
                    constraint species_banding_code_valid check (banding_code ~ '^[A-Z]{4}$')
);

comment on table species is 'Banding codes follow Bird Banding Laboratory 4-letter alpha codes.';

-- Per-species, per-year counter behind the RTHA26001 tube ID format.
-- next_seq is the value the *next* tube will use.
create table if not exists raptor_id_sequence (
    species_id integer not null references species (id) on delete cascade,
    year       integer not null,
    next_seq   integer not null default 1,
    primary key (species_id, year)
);

create table if not exists raptor_tubes (
    id                 integer primary key generated always as identity,
    tube_id            text    not null unique,
    box_id             integer not null references boxes (id) on delete cascade,
    row_pos            integer not null constraint raptor_tubes_row_valid check (row_pos >= 1),
    col_pos            integer not null constraint raptor_tubes_col_valid check (col_pos >= 1),
    species_id         integer not null references species (id) on delete restrict,
    collection_date    date    not null,
    age                text,
    sex                text,
    freeze_thaw_cycles integer not null default 0
                       constraint raptor_tubes_ft_valid check (freeze_thaw_cycles >= 0),
    wrmd_number        text,
    vmth_number        text,
    notes              text,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now(),
    unique (box_id, row_pos, col_pos)
);

comment on column raptor_tubes.tube_id is
    'Format [BAND][YY][NNN], with -N suffix when one bird yields several tubes: RTHA26001-2';

create or replace trigger raptor_tubes_set_updated_at
    before update on raptor_tubes
    for each row execute function set_updated_at();

-- ------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------

create index if not exists idx_racks_shelf            on racks (shelf_id);
create index if not exists idx_drawers_rack           on drawers (rack_id);
create index if not exists idx_boxes_drawer           on boxes (drawer_id);
create index if not exists idx_research_tubes_box     on research_tubes (box_id);
create index if not exists idx_research_tubes_sample  on research_tubes (sample_id);
create index if not exists idx_raptor_tubes_box       on raptor_tubes (box_id);
create index if not exists idx_raptor_tubes_species   on raptor_tubes (species_id);
create index if not exists idx_raptor_tubes_date      on raptor_tubes (collection_date);

-- Note: no row level security here. The only route to this data is the
-- application's own connection string, so RLS would protect nothing and would
-- get in the way of adding a read-only analysis role later.
