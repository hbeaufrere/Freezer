-- ============================================================
-- Research projects: studies that live beside the freezer, not in it.
--
-- The first kind is a CBC reference-interval study: one row per bird, one
-- pre-release hemogram each, and the interval recomputed from whatever is
-- in the table. The analytes are not fixed in the schema. They are whatever
-- the laboratory reports, kept in the order first seen, so a panel that
-- gains a line next year needs no migration.
-- ============================================================

create table if not exists studies (
    id            integer primary key generated always as identity,
    slug          text not null unique,
    name          text not null,
    kind          text not null default 'cbc_ri',
    species_code  text,
    species_name  text,
    description   text,
    -- Ordered list of {key, label, unit}: the columns of the study's table.
    analytes      jsonb not null default '[]'::jsonb,
    position      integer not null default 0,
    created_at    timestamptz not null default now()
);

create table if not exists study_cbcs (
    id            integer primary key generated always as identity,
    study_id      integer not null references studies (id) on delete cascade,
    patient_no    text,
    visit_no      text,
    wrmd_number   text,
    collected_on  date,
    age           text,
    sex           text not null default 'Unknown'
                  constraint study_cbcs_sex_valid check (sex in ('Male', 'Female', 'Unknown')),
    source        text not null default 'manual',
    -- analyte key -> number, or text for results that are not numbers.
    results       jsonb not null default '{}'::jsonb,
    notes         text,
    added_by      text,
    created_at    timestamptz not null default now()
);

comment on table study_cbcs is
    'One hemogram per bird in a reference-interval study. Values only; the statistics are computed, never stored.';

-- A reference interval counts animals, not samples: the same bird twice is
-- pseudoreplication. One row per patient per study, enforced here.
create unique index if not exists idx_study_cbcs_one_per_bird
    on study_cbcs (study_id, patient_no) where patient_no is not null;
create index if not exists idx_study_cbcs_study on study_cbcs (study_id);

insert into studies (slug, name, kind, species_code, species_name, description, position) values
    ('wtki-pre-release-ri', 'WTKI pre-release RI', 'cbc_ri', 'WTKI', 'White-tailed Kite',
     'Hematology reference intervals from pre-release CBCs.', 1),
    ('swha-pre-release-ri', 'SWHA pre-release RI', 'cbc_ri', 'SWHA', 'Swainson''s Hawk',
     'Hematology reference intervals from pre-release CBCs.', 2)
on conflict (slug) do nothing;
