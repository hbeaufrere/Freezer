-- ============================================================
-- Reference data: raptor species and the default freezer structure
--
-- Eppendorf CryoCube F740hi: 3 shelves x 6 racks x 7 drawers x 4 boxes,
-- each box a 10x10 grid = 5,040 tube positions.
--
-- Every statement is idempotent, so re-running this migration is safe.
-- ============================================================

-- ------------------------------------------------------------
-- Species
-- Banding codes follow Bird Banding Laboratory 4-letter alpha codes.
-- Taxonomy per AOS 65th/66th Supplements (2024-2025): Cooper's Hawk and
-- American Goshawk moved to Astur, Barn Owl split to American Barn Owl.
-- ------------------------------------------------------------

insert into species (common_name, scientific_name, banding_code) values
    -- Buteos
    ('Red-tailed Hawk',       'Buteo jamaicensis',         'RTHA'),
    ('Red-shouldered Hawk',   'Buteo lineatus',            'RSHA'),
    ('Broad-winged Hawk',     'Buteo platypterus',         'BWHA'),
    ('Swainson''s Hawk',      'Buteo swainsoni',           'SWHA'),
    ('Rough-legged Hawk',     'Buteo lagopus',             'RLHA'),
    ('Ferruginous Hawk',      'Buteo regalis',             'FEHA'),
    ('Zone-tailed Hawk',      'Buteo albonotatus',         'ZTHA'),
    ('White-tailed Hawk',     'Geranoaetus albicaudatus',  'WTHA'),
    ('Gray Hawk',             'Buteo plagiatus',           'GRHA'),
    ('Short-tailed Hawk',     'Buteo brachyurus',          'STHA'),
    -- Accipiters
    ('Cooper''s Hawk',        'Astur cooperii',            'COHA'),
    ('Sharp-shinned Hawk',    'Accipiter striatus',        'SSHA'),
    ('American Goshawk',      'Astur atricapillus',        'AGOS'),
    -- Harrier
    ('Northern Harrier',      'Circus hudsonius',          'NOHA'),
    -- Kites
    ('White-tailed Kite',     'Elanus leucurus',           'WTKI'),
    ('Mississippi Kite',      'Ictinia mississippiensis',  'MIKI'),
    ('Swallow-tailed Kite',   'Elanoides forficatus',      'STKI'),
    -- Parabuteo
    ('Harris''s Hawk',        'Parabuteo unicinctus',      'HRSH'),
    -- Eagles
    ('Bald Eagle',            'Haliaeetus leucocephalus',  'BAEA'),
    ('Golden Eagle',          'Aquila chrysaetos',         'GOEA'),
    -- Osprey
    ('Osprey',                'Pandion haliaetus',         'OSPR'),
    -- Falcons
    ('Peregrine Falcon',      'Falco peregrinus',          'PEFA'),
    ('Prairie Falcon',        'Falco mexicanus',           'PRFA'),
    ('American Kestrel',      'Falco sparverius',          'AMKE'),
    ('Merlin',                'Falco columbarius',         'MERL'),
    ('Gyrfalcon',             'Falco rusticolus',          'GYRF'),
    ('Aplomado Falcon',       'Falco femoralis',           'APFA'),
    ('Crested Caracara',      'Caracara plancus',          'CRCA'),
    -- Vultures
    ('Turkey Vulture',        'Cathartes aura',            'TUVU'),
    ('Black Vulture',         'Coragyps atratus',          'BLVU'),
    ('California Condor',     'Gymnogyps californianus',   'CACO'),
    -- Owls
    ('Great Horned Owl',      'Bubo virginianus',          'GHOW'),
    ('American Barn Owl',     'Tyto furcata',              'ABOW'),
    ('Barred Owl',            'Strix varia',               'BDOW'),
    ('Great Gray Owl',        'Strix nebulosa',            'GGOW'),
    ('Snowy Owl',             'Bubo scandiacus',           'SNOW'),
    ('Long-eared Owl',        'Asio otus',                 'LEOW'),
    ('Short-eared Owl',       'Asio flammeus',             'SEOW'),
    ('Northern Saw-whet Owl', 'Aegolius acadicus',         'NSWO'),
    ('Burrowing Owl',         'Athene cunicularia',        'BUOW'),
    ('Eastern Screech-Owl',   'Megascops asio',            'EASO'),
    ('Western Screech-Owl',   'Megascops kennicottii',     'WESO'),
    ('Spotted Owl',           'Strix occidentalis',        'SPOW'),
    ('Northern Pygmy-Owl',    'Glaucidium gnoma',          'NPOW'),
    ('Flammulated Owl',       'Psiloscops flammeolus',     'FLOW'),
    ('Elf Owl',               'Micrathene whitneyi',       'ELOW')
on conflict (banding_code) do nothing;

-- ------------------------------------------------------------
-- Shelves — upper shelf is the raptor biobank, the rest is research
-- ------------------------------------------------------------

insert into shelves (name, position, section) values
    ('Upper Shelf',  1, 'raptor'),
    ('Middle Shelf', 2, 'research'),
    ('Lower Shelf',  3, 'research')
on conflict (position) do nothing;

-- ------------------------------------------------------------
-- Racks — 6 per shelf. Raptor racks carry a species-group designation
-- that constrains which species the sample form offers.
-- ------------------------------------------------------------

insert into racks (shelf_id, position, label, designation)
select sh.id,
       pos.n,
       format('Rack %s%s', sh.prefix, pos.n),
       case when sh.section = 'raptor' then dsg.designation end
from (
    select id, section, case position when 1 then 'U' when 2 then 'M' else 'L' end as prefix
    from shelves
) sh
cross join generate_series(1, 6) as pos(n)
left join (values
    (1, 'RTHA / RSHA / SWHA'),
    (2, 'COHA / WTKI'),
    (3, 'GHOW / ABOW'),
    (4, 'WESO / Other Owls'),
    (5, 'AMKE / TUVU'),
    (6, 'Other Species')
) as dsg(n, designation) on dsg.n = pos.n
on conflict (shelf_id, position) do nothing;

-- ------------------------------------------------------------
-- Drawers — 7 per rack
-- ------------------------------------------------------------

insert into drawers (rack_id, position, label)
select r.id,
       pos.n,
       format('%s%s-D%s', sh.prefix, r.position, pos.n)
from racks r
join (
    select id, case position when 1 then 'U' when 2 then 'M' else 'L' end as prefix
    from shelves
) sh on sh.id = r.shelf_id
cross join generate_series(1, 7) as pos(n)
on conflict (rack_id, position) do nothing;

-- ------------------------------------------------------------
-- Boxes — 4 per drawer, 10x10 grid, inheriting their shelf's section
-- ------------------------------------------------------------

insert into boxes (drawer_id, position, label, grid_rows, grid_cols, section)
select d.id,
       pos.n,
       format('%s%s-D%s-B%s', sh.prefix, r.position, d.position, pos.n),
       10,
       10,
       sh.section
from drawers d
join racks r on r.id = d.rack_id
join (
    select id, section, case position when 1 then 'U' when 2 then 'M' else 'L' end as prefix
    from shelves
) sh on sh.id = r.shelf_id
cross join generate_series(1, 4) as pos(n)
on conflict (drawer_id, position) do nothing;
