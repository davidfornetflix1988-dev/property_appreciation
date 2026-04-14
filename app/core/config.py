from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
ZILLOW_DATA_DIR = DATA_DIR / "zillow"
FHFA_DATA_DIR = DATA_DIR / "fhfa"