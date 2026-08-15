-- ============================================================
-- Samples waiting to be collected from satellite freezers.
--
-- Raptor samples are dropped into an ordinary freezer at CRC or at VMTH and
-- collected later for the -80. Whoever drops them scans a QR code stuck to
-- that freezer, says how many they added, and the count shows up on the
-- freezer overview with the age of the oldest drop.
-- ============================================================

create table if not exists collection_sites (
    id         integer primary key generated always as identity,
    code       text not null unique,
    name       text not null,
    location   text,
    -- Unguessable; it is the only thing protecting the public drop-off page,
    -- which cannot require a login because the people using it do not have
    -- the lab password and are standing at a freezer with a phone.
    token      text not null unique,
    position   integer not null default 1,
    created_at timestamptz not null default now()
);

create table if not exists pending_dropoffs (
    id            integer primary key generated always as identity,
    site_id       integer not null references collection_sites (id) on delete cascade,
    sample_count  integer not null
                  constraint dropoffs_count_valid check (sample_count between 1 and 500),
    dropped_at    timestamptz not null default now(),
    dropped_by    text,
    note          text,
    -- Null while the samples are still sitting in the satellite freezer.
    collected_at  timestamptz,
    collected_by  text
);

comment on column pending_dropoffs.collected_at is
    'Set when the samples are moved to the -80. Rows are kept rather than '
    'deleted so the drop-off history survives collection.';

create index if not exists idx_dropoffs_site on pending_dropoffs (site_id);
-- The overview only ever asks for the uncollected ones.
create index if not exists idx_dropoffs_pending
    on pending_dropoffs (site_id, dropped_at) where collected_at is null;

-- ------------------------------------------------------------
-- The two satellite freezers
-- ------------------------------------------------------------

insert into collection_sites (code, name, location, token, position) values
    ('CRC',  'California Raptor Center',
     'Ordinary freezer, CRC', replace(gen_random_uuid()::text, '-', ''), 1),
    ('VMTH', 'Veterinary Medical Teaching Hospital',
     'Ordinary freezer, VMTH', replace(gen_random_uuid()::text, '-', ''), 2)
on conflict (code) do nothing;
