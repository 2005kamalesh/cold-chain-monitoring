"""generate -> load -> monitor, plus the reproducibility check."""
import shutil
import tempfile
from pathlib import Path

import pandas as pd

from . import db
from .config import RAW_DIR, GT_DIR, SEED
from .generator import generate


def load(raw_dir=RAW_DIR):
    """Load CSVs into the DB (parents first). Integrity is checked on the CSVs first so errors are readable."""
    from .validate import check_integrity
    raw_dir = Path(raw_dir)
    dfs = {t: pd.read_csv(raw_dir / f"{t}.csv", parse_dates=[c for c in pd.read_csv(raw_dir / f"{t}.csv", nrows=0).columns if c.endswith(db.DT_SUFFIX)])
           for t in db.INPUT_TABLES}
    gtp = GT_DIR / "ground_truth.csv"   # used only to excuse deliberately injected, labelled defects at load time
    ea = {}
    if gtp.exists():
        g = pd.read_csv(gtp)
        ea = {k: x.shipment_id.tolist() for k, x in g.groupby("issue_type")}
    bad = [c for c in check_integrity(dfs, ea) if not c["passed"]]
    if bad:
        raise SystemExit("Integrity check failed before load:\n" + "\n".join(f"  {c['name']}: {c['detail']}" for c in bad))
    db.init_schema()
    for t in db.INPUT_TABLES:
        db.write_df(t, dfs[t])
        print(f"  loaded {t:22s} {len(dfs[t]):>9,d} rows")


def reproduce(n_shipments=50, n_containers=20):
    """Generate twice with the same seed into temp dirs and compare row counts + checksums."""
    res = []
    for _ in range(2):
        d = Path(tempfile.mkdtemp())
        res.append(generate(n_shipments, n_containers, SEED, d / "raw", d / "gt")["files"])
        shutil.rmtree(d)
    ok = res[0] == res[1]
    print("Reproducibility:", "IDENTICAL" if ok else "DIFFERENT")
    for k, v in res[0].items():
        print(f"  {k:26s} rows={v['rows']:>8,d} md5={v['md5']} {'==' if v == res[1][k] else '!='} {res[1][k]['md5']}")
    return ok
