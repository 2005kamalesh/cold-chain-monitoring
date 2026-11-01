"""CLI:  python run.py all --shipments 100 --containers 30     (defaults = full assignment volume; use --shipments 100 --containers 30 for a starter set)"""
import argparse
import json

from coldchain import db, pipeline
from coldchain.config import SEED, RAW_DIR, GT_DIR
from coldchain.generator import generate

p = argparse.ArgumentParser()
p.add_argument("command", choices=["generate", "load", "monitor", "validate", "evaluate", "all", "reproduce", "docs", "export", "report"])
p.add_argument("--shipments", type=int, default=1000)
p.add_argument("--containers", type=int, default=300)
p.add_argument("--seed", type=int, default=SEED)
a = p.parse_args()

if a.command in ("generate", "all"):
    m = generate(a.shipments, a.containers, a.seed)
    print("generated:", {k: v["rows"] for k, v in m["files"].items()})
if a.command in ("load", "all"):
    pipeline.load()
if a.command in ("monitor", "all"):
    from coldchain import engine
    engine.monitor()
if a.command in ("validate", "all"):
    from coldchain import validate
    r = validate.validate()
    for c in r:
        print(("PASS " if c["passed"] else "FAIL "), c["name"], "-", c["detail"])
    print(f"{sum(c['passed'] for c in r)}/{len(r)} validation checks passed")
if a.command in ("evaluate", "all"):
    from coldchain import validate
    r = validate.evaluate()
    for k, v in r["by_issue_type"].items():
        print(f"{k:45s} {v}")
    print("shipment-level excursion detection:", r["shipment_level_excursion_detection"])
if a.command == "reproduce":
    pipeline.reproduce(a.shipments, a.containers)
if a.command == "export":
    from coldchain import export
    export.export_all()
if a.command == "report":
    from coldchain import report
    report.build_all()
if a.command == "docs":
    from coldchain import docs
    docs.write_data_dictionary()
