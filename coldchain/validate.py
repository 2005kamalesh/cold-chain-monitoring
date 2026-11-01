"""Integrity validation (PK/FK/enums/dates/reconciliation/lifecycle/duplicates/relationships) and ground-truth evaluation."""
import json

import numpy as np
import pandas as pd

from . import db
from .config import GT_DIR, DOCS_DIR, INTERVAL_MIN

PK = {"products": ["product_id"], "threshold_policies": ["policy_id"], "containers": ["container_id"], "sensors": ["sensor_id"],
      "sensor_calibrations": ["calibration_id"], "shipments": ["shipment_id"], "shipment_sensor_assignments": ["assignment_id"], "shipment_status_events": ["status_event_id"], "route_stops": ["route_stop_id"],
      "custody_events": ["custody_event_id"], "sensor_readings": ["reading_id"], "monitoring_gaps": ["gap_id"], "excursions": ["excursion_id"],
      "shipment_issues": ["issue_id"], "notifications": ["notification_id"], "corrective_actions": ["action_id"],
      "corrective_action_events": ["event_id"], "reading_flags": ["reading_id", "flag_type"], "shipment_summary": ["shipment_id"]}
FK = [("threshold_policies", "product_id", "products"), ("sensors", "container_id", "containers"), ("sensor_calibrations", "sensor_id", "sensors"),
      ("shipments", "product_id", "products"), ("shipments", "container_id", "containers"), ("shipments", "policy_id", "threshold_policies"),
      ("shipment_sensor_assignments", "shipment_id", "shipments"), ("shipment_sensor_assignments", "sensor_id", "sensors"),
      ("shipment_status_events", "shipment_id", "shipments"), ("route_stops", "shipment_id", "shipments"), ("custody_events", "shipment_id", "shipments"), ("custody_events", "route_stop_id", "route_stops"),
      ("sensor_readings", "sensor_id", "sensors"), ("sensor_readings", "shipment_id", "shipments"), ("sensor_readings", "route_stop_id", "route_stops"),
      ("reading_flags", "reading_id", "sensor_readings"), ("monitoring_gaps", "shipment_id", "shipments"), ("monitoring_gaps", "sensor_id", "sensors"),
      ("excursions", "shipment_id", "shipments"), ("excursions", "sensor_id", "sensors"), ("excursions", "policy_id", "threshold_policies"),
      ("shipment_issues", "shipment_id", "shipments"), ("notifications", "shipment_id", "shipments"), ("notifications", "excursion_id", "excursions"),
      ("notifications", "gap_id", "monitoring_gaps"), ("notifications", "issue_id", "shipment_issues"), ("corrective_actions", "excursion_id", "excursions"),
      ("corrective_action_events", "action_id", "corrective_actions"), ("shipment_summary", "shipment_id", "shipments")]
ENUMS = {("shipments", "status"): {"CREATED", "DISPATCHED", "IN_TRANSIT", "DELIVERED"}, ("sensors", "sensor_type"): {"TEMPERATURE", "HUMIDITY"},
         ("shipment_status_events", "new_status"): {"CREATED", "DISPATCHED", "IN_TRANSIT", "DELIVERED"}, ("sensors", "unit"): {"C", "%RH"}, ("sensor_calibrations", "result"): {"PASS", "FAIL"}, ("route_stops", "stop_type"): {"ORIGIN", "TRANSIT_HUB", "DESTINATION"},
         ("custody_events", "event_type"): {"DISPATCH_HANDOVER", "HUB_RECEIPT", "HUB_RELEASE", "DELIVERY_HANDOVER"},
         ("excursions", "excursion_type"): {"TEMPERATURE", "HUMIDITY"}, ("excursions", "direction"): {"HIGH", "LOW"}, ("excursions", "severity"): {"LOW", "MEDIUM", "HIGH"},
         ("excursions", "status"): {"OPEN", "UNDER_INVESTIGATION", "CLOSED"}, ("corrective_actions", "status"): {"OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "VERIFIED"},
         ("monitoring_gaps", "status"): {"UNVERIFIED"}, ("notifications", "status"): {"SENT", "ACKNOWLEDGED"}}
SHIP_NEXT = {None: "CREATED", "CREATED": "DISPATCHED", "DISPATCHED": "IN_TRANSIT", "IN_TRANSIT": "DELIVERED"}
NEXT = {None: "OPEN", "OPEN": "ASSIGNED", "ASSIGNED": "IN_PROGRESS", "IN_PROGRESS": "RESOLVED", "RESOLVED": "VERIFIED"}


def _c(name, passed, detail=""):
    return dict(name=name, passed=bool(passed), detail=str(detail))


def check_integrity(T: dict, expected_anomalies: dict = None) -> list:
    """Run every check applicable to the tables present in T. expected_anomalies (from ground truth, validation use only)
    lists shipment ids whose deliberately-injected defects are allowed to fail a rule."""
    ea = expected_anomalies or {}
    out = []
    for t, pk in PK.items():
        if t in T:
            d = T[t].duplicated(pk).sum()
            out.append(_c(f"PK unique: {t}", d == 0, f"{d} duplicates"))
    for ch, col, par in FK:
        if ch in T and par in T:
            s = T[ch][col].dropna()
            miss = (~s.isin(T[par][PK[par][0]])).sum()
            out.append(_c(f"FK valid: {ch}.{col} -> {par}", miss == 0, f"{miss} orphans"))
    for (t, col), allowed in ENUMS.items():
        if t in T:
            bad = (~T[t][col].isin(allowed)).sum()
            out.append(_c(f"Enum: {t}.{col}", bad == 0, f"{bad} invalid"))
    if {"shipments", "route_stops", "threshold_policies"} <= T.keys():
        sh = T["shipments"]
        bad = sh[sh.actual_delivery_at < sh.actual_departure_at].shipment_id
        unexpected = set(bad) - set(ea.get("DELIVERY_BEFORE_DEPARTURE", []))
        out.append(_c("Date order: delivery >= departure (excluding labelled DELIVERY_BEFORE_DEPARTURE cases)", not unexpected,
                      f"{len(bad)} violations, {len(unexpected)} unlabelled"))
        out.append(_c("Date order: planned arrival > planned departure", (sh.planned_arrival_at > sh.planned_departure_at).all()))
        rs = T["route_stops"].sort_values(["shipment_id", "stop_sequence"])
        out.append(_c("Route stop times ascend with sequence", not (rs.groupby("shipment_id").actual_arrival_at.diff() < pd.Timedelta(0)).any()))
        out.append(_c("Policy effective_from < effective_to", (T["threshold_policies"].effective_to.isna() | (T["threshold_policies"].effective_from < T["threshold_policies"].effective_to)).all()))
        pol = T["threshold_policies"]
        out.append(_c("Policies of one product do not overlap", all((g.sort_values("effective_from").effective_from.iloc[1:].values >= g.sort_values("effective_from").effective_to.iloc[:-1].values).all() for _, g in pol.groupby("product_id"))))
    if {"shipment_status_events", "shipments"} <= T.keys():
        ev = T["shipment_status_events"].sort_values(["shipment_id", "status_event_id"])
        chain_bad = {r.shipment_id for r in ev.itertuples() if SHIP_NEXT.get(None if pd.isna(r.previous_status) else r.previous_status) != r.new_status}
        time_bad = set(ev[ev.groupby("shipment_id").changed_at.diff() < pd.Timedelta(0)].shipment_id)
        unexpected = (chain_bad | time_bad) - set(ea.get("DELIVERY_BEFORE_DEPARTURE", []))
        out.append(_c("Lifecycle: shipment CREATED->DISPATCHED->IN_TRANSIT->DELIVERED in time order (labelled cases excused)", not unexpected, f"{len(chain_bad | time_bad)} violations, {len(unexpected)} unlabelled"))
    if {"shipment_sensor_assignments", "sensors", "shipments"} <= T.keys():
        a = T["shipment_sensor_assignments"].merge(T["sensors"][["sensor_id", "container_id"]], on="sensor_id").merge(T["shipments"][["shipment_id", "container_id"]], on="shipment_id", suffixes=("_s", "_h"))
        out.append(_c("Assigned sensors are installed in the shipment's container", (a.container_id_s == a.container_id_h).all()))
        have = set(T["shipment_sensor_assignments"].shipment_id)
        out.append(_c("Every shipment has a sensor assigned (monitoring coverage)", set(T["shipments"].shipment_id) <= have, f"{len(set(T['shipments'].shipment_id) - have)} uncovered"))
    if {"custody_events", "shipments"} <= T.keys():
        cs = T["custody_events"].sort_values(["shipment_id", "event_seq"])
        out.append(_c("Custody timeline ordered", not (cs.groupby("shipment_id").event_time.diff() < pd.Timedelta(0)).any()))
        m = cs[cs.event_seq == 1].merge(T["shipments"][["shipment_id", "actual_departure_at"]], on="shipment_id")
        out.append(_c("No custody event before dispatch", (m.event_time >= m.actual_departure_at).all()))
    if {"sensor_readings", "sensors", "shipments", "route_stops"} <= T.keys():
        r = T["sensor_readings"]
        out.append(_c("Duplicate readings (sensor, timestamp)", not r.duplicated(["sensor_id", "measured_at"]).any()))
        j = r[["sensor_id", "shipment_id", "route_stop_id"]].drop_duplicates().merge(T["sensors"][["sensor_id", "container_id"]], on="sensor_id").merge(
            T["shipments"][["shipment_id", "container_id"]], on="shipment_id", suffixes=("_sensor", "_ship")).merge(T["route_stops"][["route_stop_id", "shipment_id"]], on="route_stop_id", suffixes=("", "_stop"))
        out.append(_c("Readings link to the right shipment (sensor container == shipment container)", (j.container_id_sensor == j.container_id_ship).all()))
        out.append(_c("Readings link to a route stop of the same shipment", (j.shipment_id == j.shipment_id_stop).all()))
        sh = T["shipments"].sort_values(["container_id", "actual_departure_at"])
        sh = sh[~sh.shipment_id.isin(ea.get("DELIVERY_BEFORE_DEPARTURE", []))]
        ov = sh.groupby("container_id").apply(lambda g: (g.actual_departure_at.iloc[1:].values < g.actual_delivery_at.iloc[:-1].values).sum(), include_groups=False).sum()
        out.append(_c("No container assigned to overlapping shipments", ov == 0, f"{ov} overlaps"))
    return out


def validate(write_report=True) -> list:
    T = {t: db.read_table(t) for t in list(PK)}
    gt = pd.read_csv(GT_DIR / "ground_truth.csv") if (GT_DIR / "ground_truth.csv").exists() else pd.DataFrame(columns=["issue_type", "shipment_id"])
    ea = {k: g.shipment_id.tolist() for k, g in gt.groupby("issue_type")}  # used ONLY to excuse deliberately injected defects
    out = check_integrity(T, ea)
    ex, gp, rd = T["excursions"], T["monitoring_gaps"], T["sensor_readings"]
    out.append(_c("Reconcile: excursion duration == (ended - started) minutes", (((ex.ended_at - ex.started_at) / pd.Timedelta(minutes=1)).round() == ex.duration_minutes).all()))
    out.append(_c("Reconcile: actionable <=> duration > permissible", ((ex.duration_minutes > ex.max_permissible_minutes).astype(int) == ex.is_actionable).all()))
    out.append(_c("Reconcile: gap missing_intervals == gap_minutes/5 - 1", (gp.gap_minutes // INTERVAL_MIN - 1 == gp.missing_intervals).all()))
    sh = T["shipments"]
    sh = sh[~sh.shipment_id.isin(ea.get("DELIVERY_BEFORE_DEPARTURE", []))]
    exp = ((sh.actual_delivery_at - sh.actual_departure_at) / pd.Timedelta(minutes=INTERVAL_MIN)).astype(int) + 1
    got = rd.groupby("shipment_id").size() / 2
    miss = gp.groupby("shipment_id").missing_intervals.sum().reindex(sh.shipment_id).fillna(0).values / 2
    exp_n = exp.values
    diff = np.abs(exp_n - (got.reindex(sh.shipment_id).fillna(0).values + miss))
    out.append(_c("Reconcile: expected intervals == received + missing (per shipment, both sensors averaged)", (diff < 1e-9).all() or (diff <= 0.5).all(), f"max diff {diff.max() if len(diff) else 0}"))
    out.append(_c("Reconcile: summary excursion_count == excursions rows", T["shipment_summary"].excursion_count.sum() == len(ex)))
    ev = T["corrective_action_events"].sort_values(["action_id", "changed_at", "event_id"])
    ok = True
    for aid, g in ev.groupby("action_id"):
        prev = None
        for r in g.itertuples():
            ok &= (r.previous_status == prev or (prev is None and pd.isna(r.previous_status))) and NEXT[prev] == r.new_status
            prev = r.new_status
    out.append(_c("Lifecycle: corrective action OPEN->ASSIGNED->IN_PROGRESS->RESOLVED->VERIFIED, no skipped/VERIFIED-without-RESOLVED", ok))
    last = ev.groupby("action_id").new_status.last()
    out.append(_c("Lifecycle: action.status == last history event", (T["corrective_actions"].set_index("action_id").status == last.reindex(T["corrective_actions"].action_id).values).all()))
    out.append(_c("Every actionable excursion has >=1 corrective action and a notification", set(ex[ex.is_actionable == 1].excursion_id) <= set(T["corrective_actions"].excursion_id) and set(ex.excursion_id) <= set(T["notifications"].excursion_id.dropna())))
    out.append(_c("Excursion duplicates (shipment, sensor, start)", not ex.duplicated(["shipment_id", "sensor_id", "started_at"]).any()))
    if write_report:
        DOCS_DIR.mkdir(exist_ok=True)
        (DOCS_DIR / "validation_report.json").write_text(json.dumps(out, indent=2))
        lines = ["# Validation report", "", f"{sum(c['passed'] for c in out)}/{len(out)} checks passed", "", "| Check | Result | Detail |", "|---|---|---|"]
        lines += [f"| {c['name']} | {'PASS' if c['passed'] else 'FAIL'} | {c['detail']} |" for c in out]
        (DOCS_DIR / "validation_report.md").write_text("\n".join(lines) + "\n")
    return out


# ------------------------------------------------------------------ evaluation vs ground truth
def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return dict(TP=int(tp), FP=int(fp), FN=int(fn), precision=round(float(p), 4), recall=round(float(r), 4), f1=round(float(2 * p * r / (p + r)), 4) if p + r else 0.0)


def evaluate(write_report=True) -> dict:
    """Instance-level evaluation (one anomaly = one unit). Ground truth is read ONLY here, never by the engine."""
    gt = pd.read_csv(GT_DIR / "ground_truth.csv", parse_dates=["expected_start", "expected_end"])
    ex, gp, fl, iss = (db.read_table(t) for t in ("excursions", "monitoring_gaps", "reading_flags", "shipment_issues"))
    sh = db.read_table("shipments")
    res, errs = {}, {}
    for typ in ("TEMPERATURE", "HUMIDITY"):
        g = gt[gt.issue_type == f"{typ}_EXCURSION"]
        e = ex[ex.excursion_type == typ]
        m = g.merge(e, left_on=["shipment_id", "sensor_id", "expected_start"], right_on=["shipment_id", "sensor_id", "started_at"], how="left")
        tp = m.excursion_id.notna()
        fp = len(e) - tp.sum()
        res[f"{typ}_EXCURSION"] = _prf(tp.sum(), fp, (~tp).sum())
        mm = m[tp]
        errs[typ] = dict(matched=int(tp.sum()), duration_abs_error_min_max=float((mm.duration_minutes - mm.expected_duration_minutes).abs().max()) if len(mm) else 0.0,
                         end_time_exact=float((mm.ended_at == mm.expected_end).mean()) if len(mm) else 1.0,
                         severity_accuracy=float((mm.severity == mm.expected_severity).mean()) if len(mm) else 1.0,
                         actionable_accuracy=float((mm.is_actionable.astype(bool) == mm.expected_actionable.astype(bool)).mean()) if len(mm) else 1.0)
    g = gt[gt.issue_type == "MISSING_INTERVAL"]
    m = g.merge(gp, left_on=["shipment_id", "sensor_id", "expected_start"], right_on=["shipment_id", "sensor_id", "gap_start"], how="left")
    tp = m.gap_id.notna()
    res["MISSING_INTERVAL"] = _prf(tp.sum(), len(gp) - tp.sum(), (~tp).sum())
    errs["MISSING_INTERVAL"] = dict(missing_interval_count_exact=float((m[tp].missing_intervals == m[tp].expected_missing_intervals).mean()) if tp.any() else 1.0,
                                    tolerance_flag_accuracy=float((m[tp].exceeds_tolerance.astype(bool) == m[tp].expected_actionable.astype(bool)).mean()) if tp.any() else 1.0)
    g = gt[gt.issue_type == "PHYSICAL_RANGE_VIOLATION"]
    f = fl[fl.flag_type == "PHYSICAL_RANGE_VIOLATION"]
    res["PHYSICAL_RANGE_VIOLATION"] = _prf(g.reading_id.isin(f.reading_id).sum(), (~f.reading_id.isin(g.reading_id)).sum(), (~g.reading_id.isin(f.reading_id)).sum())
    for typ in ("DELIVERY_BEFORE_DEPARTURE", "POLICY_MISMATCH", "ROUTE_DELAY"):
        g, f = set(gt[gt.issue_type == typ].shipment_id), set(iss[iss.issue_type == typ].shipment_id)
        res[typ] = _prf(len(g & f), len(f - g), len(g - f))
    for typ in ("CALIBRATION_EXPIRED", "LATE_ARRIVAL"):
        g = gt[gt.issue_type == typ].set_index(["shipment_id", "sensor_id"]).expected_count
        f = iss[iss.issue_type == typ].assign(n=lambda d: d.detail.str.extract(r"(\d+)$")[0].astype(int)).set_index(["shipment_id", "sensor_id"]).n
        tp = sum(1 for k in g.index if k in f.index and int(f[k]) == int(g[k]))
        res[typ] = _prf(tp, len(set(f.index) - set(g.index)) + (len(set(f.index) & set(g.index)) - tp), len(g) - tp)
    b = gt[gt.issue_type == "BOUNDARY_INCLUSIVE"]
    bb = b.merge(ex[["shipment_id", "started_at", "ended_at"]], on="shipment_id", how="left")
    hit = bb[(bb.started_at <= bb.expected_end) & (bb.ended_at >= bb.expected_start)]
    res["BOUNDARY_INCLUSIVE (no excursion expected)"] = dict(cases=len(b), false_excursions=int(len(hit)), passed=bool(len(hit) == 0))
    ship_gt = set(gt[gt.issue_type.isin(["TEMPERATURE_EXCURSION", "HUMIDITY_EXCURSION"])].shipment_id)
    ship_det = set(ex.shipment_id)
    tp, fp, fn = len(ship_gt & ship_det), len(ship_det - ship_gt), len(ship_gt - ship_det)
    shipment_level = dict(**_prf(tp, fp, fn), TN=int(len(sh) - tp - fp - fn))
    out = dict(level="instance (1 injected anomaly = 1 unit); shipment-level confusion matrix reported separately for excursions",
               by_issue_type=res, timing_and_label_errors=errs, shipment_level_excursion_detection=shipment_level)
    if write_report:
        DOCS_DIR.mkdir(exist_ok=True)
        (DOCS_DIR / "evaluation_report.json").write_text(json.dumps(out, indent=2, default=str))
        L = ["# Detection evaluation vs ground truth", "", out["level"], "", "| Issue type | TP | FP | FN | Precision | Recall | F1 |", "|---|---|---|---|---|---|---|"]
        for k, v in res.items():
            L.append(f"| {k} | " + (" | ".join(str(v[x]) for x in ("TP", "FP", "FN", "precision", "recall", "f1")) if "TP" in v else f"cases={v['cases']}, false excursions={v['false_excursions']} | | | | |") + " |")
        L += ["", "## Timing / label accuracy (matched excursions)", "```", json.dumps(errs, indent=2), "```", "", "## Shipment-level excursion detection", "```", json.dumps(shipment_level, indent=2), "```"]
        (DOCS_DIR / "evaluation_report.md").write_text("\n".join(L) + "\n")
    return out
