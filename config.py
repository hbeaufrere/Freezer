import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'db', 'freezer.db')

# Freezer physical constants
NUM_SHELVES = 3
RACKS_PER_SHELF = 6
DRAWERS_PER_RACK = 7
BOXES_PER_DRAWER = 4
DEFAULT_GRID_ROWS = 9
DEFAULT_GRID_COLS = 9

# Shelf assignments
RAPTOR_SHELF_POSITION = 1   # Upper shelf
RESEARCH_SHELF_POSITIONS = [2, 3]  # Middle and lower shelves

# Raptor ID format
RAPTOR_ID_SEQ_DIGITS = 3  # Zero-padded to 3 digits: 001-999

# Age options for raptor biobank
AGE_OPTIONS = ['Adult', 'Subadult', 'Juvenile', 'Hatch Year', 'After Hatch Year', 'Unknown']

# Sex options
SEX_OPTIONS = ['Male', 'Female', 'Unknown']
