-- ============================================================
-- Biorepository Freezer — Postgres schema (Supabase)
-- ============================================================

-- ============================================================
-- USERS & AUTH
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id                      SERIAL PRIMARY KEY,
    email                   TEXT NOT NULL UNIQUE,
    full_name               TEXT,
    password_hash           TEXT NOT NULL,
    role                    TEXT NOT NULL CHECK (role IN ('admin', 'raptor', 'clipr', 'both')),
    must_change_password    BOOLEAN NOT NULL DEFAULT TRUE,
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at           TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(LOWER(email));

-- ============================================================
-- FREEZER PHYSICAL STRUCTURE
-- Hierarchy: Shelf -> Rack -> Drawer -> Box -> Tube positions
-- ============================================================

CREATE TABLE IF NOT EXISTS shelves (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    position    INTEGER NOT NULL UNIQUE,
    section     TEXT NOT NULL DEFAULT 'research' CHECK (section IN ('raptor', 'research'))
);

CREATE TABLE IF NOT EXISTS racks (
    id          SERIAL PRIMARY KEY,
    shelf_id    INTEGER NOT NULL REFERENCES shelves(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    label       TEXT,
    designation TEXT,
    UNIQUE(shelf_id, position)
);

CREATE TABLE IF NOT EXISTS drawers (
    id          SERIAL PRIMARY KEY,
    rack_id     INTEGER NOT NULL REFERENCES racks(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    label       TEXT,
    UNIQUE(rack_id, position)
);

CREATE TABLE IF NOT EXISTS boxes (
    id          SERIAL PRIMARY KEY,
    drawer_id   INTEGER NOT NULL REFERENCES drawers(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    label       TEXT,
    grid_rows   INTEGER NOT NULL DEFAULT 10,
    grid_cols   INTEGER NOT NULL DEFAULT 10,
    section     TEXT NOT NULL DEFAULT 'research' CHECK (section IN ('raptor', 'research')),
    UNIQUE(drawer_id, position)
);

-- ============================================================
-- RESEARCH SECTION TUBES
-- ============================================================

CREATE TABLE IF NOT EXISTS research_tubes (
    id                  SERIAL PRIMARY KEY,
    box_id              INTEGER NOT NULL REFERENCES boxes(id) ON DELETE CASCADE,
    row_pos             INTEGER NOT NULL,
    col_pos             INTEGER NOT NULL,
    sample_id           TEXT,
    description         TEXT,
    date_stored         DATE,
    freeze_thaw_cycles  INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(box_id, row_pos, col_pos)
);

-- ============================================================
-- RAPTOR BIOBANK SECTION
-- ============================================================

CREATE TABLE IF NOT EXISTS species (
    id              SERIAL PRIMARY KEY,
    common_name     TEXT NOT NULL,
    scientific_name TEXT NOT NULL,
    banding_code    TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS raptor_id_sequence (
    species_id  INTEGER NOT NULL REFERENCES species(id),
    year        INTEGER NOT NULL,
    next_seq    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (species_id, year)
);

CREATE TABLE IF NOT EXISTS raptor_tubes (
    id                  SERIAL PRIMARY KEY,
    tube_id             TEXT NOT NULL UNIQUE,
    box_id              INTEGER NOT NULL REFERENCES boxes(id) ON DELETE CASCADE,
    row_pos             INTEGER NOT NULL,
    col_pos             INTEGER NOT NULL,
    species_id          INTEGER NOT NULL REFERENCES species(id),
    collection_date     DATE NOT NULL,
    age                 TEXT,
    sex                 TEXT,
    freeze_thaw_cycles  INTEGER NOT NULL DEFAULT 0,
    wrmd_number         TEXT,
    vmth_number         TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(box_id, row_pos, col_pos)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_research_tubes_box ON research_tubes(box_id);
CREATE INDEX IF NOT EXISTS idx_raptor_tubes_box ON raptor_tubes(box_id);
CREATE INDEX IF NOT EXISTS idx_raptor_tubes_species ON raptor_tubes(species_id);
CREATE INDEX IF NOT EXISTS idx_raptor_tubes_tube_id ON raptor_tubes(tube_id);
CREATE INDEX IF NOT EXISTS idx_raptor_tubes_date ON raptor_tubes(collection_date);
CREATE INDEX IF NOT EXISTS idx_boxes_drawer ON boxes(drawer_id);
CREATE INDEX IF NOT EXISTS idx_drawers_rack ON drawers(rack_id);
CREATE INDEX IF NOT EXISTS idx_racks_shelf ON racks(shelf_id);
