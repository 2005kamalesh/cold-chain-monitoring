"""Negative/edge scenarios: tamper with a copy of the valid dataset and assert the validators catch each fault.
Needs data/raw generated first (python run.py generate --shipments 100 --containers 30). Run: python tests/test_negative_cases.py"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from coldchain import db  # noqa: E402
from coldchain.config import RAW_DIR  # noqa: E402
from coldchain.validate import check_integrity  # noqa: E402


def load():
    T = {}
    for t in db.INPUT_TABLES:
        cols = pd.read_csv(RAW_DIR / f"{t}.csv", nrows=0).columns
        T[t] = pd.read_csv(RAW_DIR / f"{t}.csv", parse_dates=[c for c in cols if c.endswith(db.DT_SUFFIX)])
    return T


def failing(T, ea=None):
    return [c["name"] for c in check_integrity(T, ea) if not c["passed"]]


def test_baseline_only_labelled_defect():
    T = load()
    import pandas as pd
    gt = pd.read_csv(RAW_DIR.parent / "ground_truth" / "ground_truth.csv")
    ea = {k: g.shipment_id.tolist() for k, g in gt.groupby("issue_type")}
    assert failing(T, ea) == []


def test_custody_event_before_dispatch_and_out_of_order():
    T = load(); c = T["custody_events"]; i = c.index[c.event_seq == 2][0]
    c.loc[i, "event_time"] = c.loc[i, "event_time"] - pd.Timedelta(days=30)
    assert any("Custody" in n or "custody" in n for n in failing(T, {"DELIVERY_BEFORE_DEPARTURE": []}))


def test_route_stops_wrong_order():
    T = load(); r = T["route_stops"]; i = r.index[r.stop_sequence == 2][0]
    r.loc[i, "actual_arrival_at"] = r.loc[i, "actual_arrival_at"] - pd.Timedelta(days=30)
    assert any("Route stop" in n for n in failing(T, {}))


def test_container_assigned_to_overlapping_shipments():
    T = load(); s = T["shipments"]; a, b = s.index[0], s.index[1]
    s.loc[b, "container_id"] = s.loc[a, "container_id"]; s.loc[b, "actual_departure_at"] = s.loc[a, "actual_departure_at"] + pd.Timedelta(hours=1)
    assert any("overlapping" in n for n in failing(T, {}))


def test_duplicate_reading_and_duplicate_id():
    T = load(); r = T["sensor_readings"]; T["sensor_readings"] = pd.concat([r, r.iloc[[0]]], ignore_index=True)
    f = failing(T, {})
    assert any("PK unique: sensor_readings" in n for n in f) and any("Duplicate readings" in n for n in f)


def test_orphan_sensor_and_orphan_shipment():
    T = load(); r = T["sensor_readings"]; r.loc[0, "sensor_id"] = "SNS-CNT-999999-TEMP"; r.loc[1, "shipment_id"] = "SHP-2026-999999"
    f = failing(T, {})
    assert any("sensor_readings.sensor_id" in n for n in f) and any("sensor_readings.shipment_id" in n for n in f)


def test_shipment_without_sensor_assignment():
    T = load(); a = T["shipment_sensor_assignments"]; T["shipment_sensor_assignments"] = a[a.shipment_id != a.shipment_id.iloc[0]]
    assert any("sensor assigned" in n for n in failing(T, {}))


def test_shipment_lifecycle_skip_and_invalid_enum():
    T = load(); e = T["shipment_status_events"]; i = e.index[e.new_status == "IN_TRANSIT"][0]
    e.loc[i, "new_status"] = "TELEPORTED"
    assert any("Enum: shipment_status_events" in n for n in failing(T, {}))
    T = load(); e = T["shipment_status_events"]; T["shipment_status_events"] = e[~((e.shipment_id == e.shipment_id.iloc[0]) & (e.new_status == "DISPATCHED"))]
    assert any("Lifecycle: shipment" in n for n in failing(T, {}))


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok ", n)
