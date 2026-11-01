"""Central configuration. Every business-rule constant lives here and is documented in docs/business_rules.md."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261022

# ---- monitoring conventions -------------------------------------------------
INTERVAL_MIN = 5            # expected reading interval
GAP_TOLERANCE_MIN = 15      # a gap (next_ts - prev_ts) strictly greater than this raises an alert
LATE_ARRIVAL_MIN = 30       # received_at - measured_at strictly greater than this => LATE_ARRIVAL
DELAY_THRESHOLD_MIN = 60    # delivery later than plan by more than this => ROUTE_DELAY
PHYSICAL_RANGE = {"TEMPERATURE": (-50.0, 60.0), "HUMIDITY": (0.0, 100.0)}  # plausibility, NOT product limits

# ---- database ---------------------------------------------------------------
# SQLite (zero setup):  sqlite:///cold_chain.db
# MySQL:                mysql://user:password@localhost:3306/cold_chain
DB_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'cold_chain.db'}")

DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
GT_DIR = DATA_DIR / "ground_truth"
EXPORT_DIR = DATA_DIR / "exports"
DERIVED_DIR = DATA_DIR / "derived"
DOCS_DIR = ROOT / "docs"
