-- Common North American raptors encountered in wildlife rehabilitation
-- Banding codes follow the Bird Banding Laboratory (BBL) 4-letter alpha codes
-- Taxonomy updated per AOS 65th/66th Supplements (2024-2025)

-- Hawks (Buteos)
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Red-tailed Hawk', 'Buteo jamaicensis', 'RTHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Red-shouldered Hawk', 'Buteo lineatus', 'RSHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Broad-winged Hawk', 'Buteo platypterus', 'BWHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Swainson''s Hawk', 'Buteo swainsoni', 'SWHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Rough-legged Hawk', 'Buteo lagopus', 'RLHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Ferruginous Hawk', 'Buteo regalis', 'FEHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Zone-tailed Hawk', 'Buteo albonotatus', 'ZTHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('White-tailed Hawk', 'Geranoaetus albicaudatus', 'WTHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Gray Hawk', 'Buteo plagiatus', 'GRHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Short-tailed Hawk', 'Buteo brachyurus', 'STHA') ON CONFLICT (banding_code) DO NOTHING;

-- Accipiters (AOS 65th Supplement: Cooper's Hawk and American Goshawk moved to genus Astur)
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Cooper''s Hawk', 'Astur cooperii', 'COHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Sharp-shinned Hawk', 'Accipiter striatus', 'SSHA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('American Goshawk', 'Astur atricapillus', 'AGOS') ON CONFLICT (banding_code) DO NOTHING;

-- Harrier
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Northern Harrier', 'Circus hudsonius', 'NOHA') ON CONFLICT (banding_code) DO NOTHING;

-- Kites
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('White-tailed Kite', 'Elanus leucurus', 'WTKI') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Mississippi Kite', 'Ictinia mississippiensis', 'MIKI') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Swallow-tailed Kite', 'Elanoides forficatus', 'STKI') ON CONFLICT (banding_code) DO NOTHING;

-- Harris's Hawk
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Harris''s Hawk', 'Parabuteo unicinctus', 'HRSH') ON CONFLICT (banding_code) DO NOTHING;

-- Eagles
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Bald Eagle', 'Haliaeetus leucocephalus', 'BAEA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Golden Eagle', 'Aquila chrysaetos', 'GOEA') ON CONFLICT (banding_code) DO NOTHING;

-- Osprey
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Osprey', 'Pandion haliaetus', 'OSPR') ON CONFLICT (banding_code) DO NOTHING;

-- Falcons
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Peregrine Falcon', 'Falco peregrinus', 'PEFA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Prairie Falcon', 'Falco mexicanus', 'PRFA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('American Kestrel', 'Falco sparverius', 'AMKE') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Merlin', 'Falco columbarius', 'MERL') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Gyrfalcon', 'Falco rusticolus', 'GYRF') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Aplomado Falcon', 'Falco femoralis', 'APFA') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Crested Caracara', 'Caracara plancus', 'CRCA') ON CONFLICT (banding_code) DO NOTHING;

-- Vultures
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Turkey Vulture', 'Cathartes aura', 'TUVU') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Black Vulture', 'Coragyps atratus', 'BLVU') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('California Condor', 'Gymnogyps californianus', 'CACO') ON CONFLICT (banding_code) DO NOTHING;

-- Owls (AOS 66th Supplement: Barn Owl split, now American Barn Owl)
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Great Horned Owl', 'Bubo virginianus', 'GHOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('American Barn Owl', 'Tyto furcata', 'ABOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Barred Owl', 'Strix varia', 'BDOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Great Gray Owl', 'Strix nebulosa', 'GGOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Snowy Owl', 'Bubo scandiacus', 'SNOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Long-eared Owl', 'Asio otus', 'LEOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Short-eared Owl', 'Asio flammeus', 'SEOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Northern Saw-whet Owl', 'Aegolius acadicus', 'NSWO') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Burrowing Owl', 'Athene cunicularia', 'BUOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Eastern Screech-Owl', 'Megascops asio', 'EASO') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Western Screech-Owl', 'Megascops kennicottii', 'WESO') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Spotted Owl', 'Strix occidentalis', 'SPOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Northern Pygmy-Owl', 'Glaucidium gnoma', 'NPOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Flammulated Owl', 'Psiloscops flammeolus', 'FLOW') ON CONFLICT (banding_code) DO NOTHING;
INSERT INTO species (common_name, scientific_name, banding_code) VALUES ('Elf Owl', 'Micrathene whitneyi', 'ELOW') ON CONFLICT (banding_code) DO NOTHING;
