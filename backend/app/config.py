from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
GIOVANNI_CSV = DATA_DIR / "fusion-Yaounde.csv"
REGIONAL_JSON = DATA_DIR / "years.json"
DATASET_VERSION = "observations-1"
MANN_KENDALL_ALPHA = 0.05
MIN_SAMPLES = 8
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
