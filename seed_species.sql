-- Common North American raptors encountered in wildlife rehabilitation
-- Banding codes follow the Bird Banding Laboratory (BBL) 4-letter alpha codes
-- Taxonomy updated per AOS 65th/66th Supplements (2024-2025)

-- Hawks (Buteos)
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Red-tailed Hawk', 'Buteo jamaicensis', 'RTHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Red-shouldered Hawk', 'Buteo lineatus', 'RSHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Broad-winged Hawk', 'Buteo platypterus', 'BWHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Swainson''s Hawk', 'Buteo swainsoni', 'SWHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Rough-legged Hawk', 'Buteo lagopus', 'RLHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Ferruginous Hawk', 'Buteo regalis', 'FEHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Zone-tailed Hawk', 'Buteo albonotatus', 'ZTHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('White-tailed Hawk', 'Geranoaetus albicaudatus', 'WTHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Gray Hawk', 'Buteo plagiatus', 'GRHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Short-tailed Hawk', 'Buteo brachyurus', 'STHA');

-- Accipiters (AOS 65th Supplement: Cooper's Hawk and American Goshawk moved to genus Astur)
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Cooper''s Hawk', 'Astur cooperii', 'COHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Sharp-shinned Hawk', 'Accipiter striatus', 'SSHA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('American Goshawk', 'Astur atricapillus', 'AGOS');

-- Harrier
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Northern Harrier', 'Circus hudsonius', 'NOHA');

-- Kites
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('White-tailed Kite', 'Elanus leucurus', 'WTKI');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Mississippi Kite', 'Ictinia mississippiensis', 'MIKI');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Swallow-tailed Kite', 'Elanoides forficatus', 'STKI');

-- Harris's Hawk
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Harris''s Hawk', 'Parabuteo unicinctus', 'HRSH');

-- Eagles
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Bald Eagle', 'Haliaeetus leucocephalus', 'BAEA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Golden Eagle', 'Aquila chrysaetos', 'GOEA');

-- Osprey
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Osprey', 'Pandion haliaetus', 'OSPR');

-- Falcons
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Peregrine Falcon', 'Falco peregrinus', 'PEFA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Prairie Falcon', 'Falco mexicanus', 'PRFA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('American Kestrel', 'Falco sparverius', 'AMKE');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Merlin', 'Falco columbarius', 'MERL');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Gyrfalcon', 'Falco rusticolus', 'GYRF');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Aplomado Falcon', 'Falco femoralis', 'APFA');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Crested Caracara', 'Caracara plancus', 'CRCA');

-- Vultures
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Turkey Vulture', 'Cathartes aura', 'TUVU');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Black Vulture', 'Coragyps atratus', 'BLVU');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('California Condor', 'Gymnogyps californianus', 'CACO');

-- Owls (AOS 66th Supplement: Barn Owl split, now American Barn Owl)
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Great Horned Owl', 'Bubo virginianus', 'GHOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('American Barn Owl', 'Tyto furcata', 'ABOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Barred Owl', 'Strix varia', 'BDOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Great Gray Owl', 'Strix nebulosa', 'GGOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Snowy Owl', 'Bubo scandiacus', 'SNOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Long-eared Owl', 'Asio otus', 'LEOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Short-eared Owl', 'Asio flammeus', 'SEOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Northern Saw-whet Owl', 'Aegolius acadicus', 'NSWO');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Burrowing Owl', 'Athene cunicularia', 'BUOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Eastern Screech-Owl', 'Megascops asio', 'EASO');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Western Screech-Owl', 'Megascops kennicottii', 'WESO');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Spotted Owl', 'Strix occidentalis', 'SPOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Northern Pygmy-Owl', 'Glaucidium gnoma', 'NPOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Flammulated Owl', 'Psiloscops flammeolus', 'FLOW');
INSERT OR IGNORE INTO species (common_name, scientific_name, banding_code) VALUES ('Elf Owl', 'Micrathene whitneyi', 'ELOW');
