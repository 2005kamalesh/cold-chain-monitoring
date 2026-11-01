"""Monitoring & business-logic engine. Reads ONLY the input tables (never ground truth) and writes derived tables.

Conventions (see docs/business_rules.md):
  * limits are inclusive (value == limit is in range)
  * excursion start = first valid out-of-range reading; end = first subsequent valid in-range reading
    (duration = end - start, from timestamps, never count*5). Missing/invalid readings neither start nor end an excursion.
  * excursion ends END_OF_DATA at last violating reading + interval if no recovery reading exists
  * permissible duration is CONSECUTIVE; actionable only if duration is STRICTLY greater than the limit
  * missing readings are UNVERIFIED, never safe; invalid (physically impossible) readings are preserved but excluded
"""
import numpy as np
import pandas as pd

from . import db
from .config import (SEED, INTERVAL_MIN, GAP_TOLERANCE_MIN, LATE_ARRIVAL_MIN, DELAY_THRESHOLD_MIN, PHYSICAL_RANGE, DERIVED_DIR)

ISSUE_ROLE = {"DELIVERY_BEFORE_DEPARTURE": "OT_IT_ADMIN", "POLICY_MISMATCH": "QUALITY_ENGINEER", "ROUTE_DELAY": "PRODUCTION_PLANNER",
              "CALIBRATION_EXPIRED": "OT_IT_ADMIN", "LATE_ARRIVAL": "OT_IT_ADMIN", "NO_MONITORING_DATA": "MAINTENANCE_ENGINEER",
              "ROUTE_SEQUENCE_ERROR": "QUALITY_ENGINEER", "CUSTODY_ORDER_ERROR": "QUALITY_ENGINEER",
              "READING_SENSOR_MISMATCH": "OT_IT_ADMIN", "PHYSICAL_RANGE_VIOLATION": "OT_IT_ADMIN"}
ISSUE_SEV = {"DELIVERY_BEFORE_DEPARTURE": "HIGH", "POLICY_MISMATCH": "HIGH", "ROUTE_DELAY": "MEDIUM", "CALIBRATION_EXPIRED": "MEDIUM",
             "LATE_ARRIVAL": "LOW", "NO_MONITORING_DATA": "HIGH", "ROUTE_SEQUENCE_ERROR": "MEDIUM", "CUSTODY_ORDER_ERROR": "MEDIUM",
             "READING_SENSOR_MISMATCH": "HIGH", "PHYSICAL_RANGE_VIOLATION": "MEDIUM"}
RECORD_ERRORS = {"DELIVERY_BEFORE_DEPARTURE", "POLICY_MISMATCH", "ROUTE_SEQUENCE_ERROR", "CUSTODY_ORDER_ERROR", "READING_SENSOR_MISMATCH"}
ACTION_FLOW = ["OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "VERIFIED"]
EMPTY_EXC = ["shipment_id", "sensor_id", "policy_id", "route_stop_id", "sensor_type", "direction", "started_at", "ended_at",
             "end_reason", "peak_value", "limit_value", "max_permissible_minutes", "reading_count", "has_internal_gap",
             "data_quality", "duration_minutes", "is_actionable", "severity", "excursion_type"]


def find_excursions(vr: pd.DataFrame) -> pd.DataFrame:
    """Core detector. vr = VALID readings sorted by (shipment_id, sensor_id, measured_at) with columns:
    shipment_id, sensor_id, measured_at, reading_value, lo, hi, policy_id, max_excursion_minutes, sensor_type,
    questionable, route_stop_id."""
    vr = vr.reset_index(drop=True)
    if vr.empty:
        return pd.DataFrame(columns=EMPTY_EXC)
    v, lo, hi = vr.reading_value.values, vr.lo.values, vr.hi.values
    d = np.where(v > hi, 1, np.where(v < lo, -1, 0))                       # inclusive limits
    key = vr.groupby(["shipment_id", "sensor_id"], sort=False).ngroup().values
    same = np.r_[False, key[1:] == key[:-1]]
    prev = np.where(same, np.r_[0, d[:-1]], 0)
    start = (d != 0) & (d != prev)
    if not start.any():
        return pd.DataFrame(columns=EMPTY_EXC)
    run = np.where(d != 0, np.cumsum(start), 0)
    ts = vr.measured_at.values
    gapb = same & np.r_[False, (ts[1:] - ts[:-1]) > np.timedelta64(INTERVAL_MIN, "m")]
    cg = np.cumsum(gapb)
    dev = np.where(d == 1, v - hi, lo - v)
    nz = np.where(d != 0)[0]
    viol = pd.DataFrame({"run": run[nz], "idx": nz, "dev": dev[nz], "q": vr.questionable.values[nz].astype(int)}, index=nz)
    agg = viol.groupby("run").agg(first=("idx", "min"), last=("idx", "max"), n=("idx", "size"), q=("q", "max"), pk=("dev", "idxmax"))
    f, l = agg["first"].values, agg["last"].values
    nxt = np.minimum(l + 1, len(vr) - 1)
    has_next = (l + 1 < len(vr)) & (key[nxt] == key[l])
    end_ts = np.where(has_next, ts[nxt], ts[l] + np.timedelta64(INTERVAL_MIN, "m"))
    reason = np.where(has_next, np.where(d[nxt] == 0, "RECOVERED", "DIRECTION_CHANGE"), "END_OF_DATA")
    out = pd.DataFrame({
        "shipment_id": vr.shipment_id.values[f], "sensor_id": vr.sensor_id.values[f], "policy_id": vr.policy_id.values[f],
        "route_stop_id": vr.route_stop_id.values[f], "sensor_type": vr.sensor_type.values[f],
        "direction": np.where(d[f] == 1, "HIGH", "LOW"), "started_at": ts[f], "ended_at": end_ts, "end_reason": reason,
        "peak_value": v[agg["pk"].values], "limit_value": np.where(d[f] == 1, hi[f], lo[f]),
        "max_permissible_minutes": vr.max_excursion_minutes.values[f].astype(int), "reading_count": agg["n"].values,
        "has_internal_gap": (((cg[l] - cg[f]) > 0) | (has_next & gapb[nxt])).astype(int),
        "data_quality": np.where(agg["q"].values > 0, "QUESTIONABLE", "OK")})
    out["duration_minutes"] = ((out.ended_at - out.started_at) / np.timedelta64(1, "m")).round().astype(int)
    out["is_actionable"] = (out.duration_minutes > out.max_permissible_minutes).astype(int)
    out["severity"] = np.where(out.is_actionable == 0, "LOW", np.where(out.duration_minutes <= 2 * out.max_permissible_minutes, "MEDIUM", "HIGH"))
    out["excursion_type"] = out.sensor_type
    return out


def find_gaps(a: pd.DataFrame) -> pd.DataFrame:
    """a = ALL received readings sorted by (shipment_id, sensor_id, measured_at). A gap = consecutive timestamps > interval apart."""
    key = a.groupby(["shipment_id", "sensor_id"], sort=False).ngroup().values
    dt = a.measured_at.diff()
    mask = np.r_[False, key[1:] == key[:-1]] & (dt > pd.Timedelta(minutes=INTERVAL_MIN)).values
    g = pd.DataFrame({"shipment_id": a.shipment_id[mask].values, "sensor_id": a.sensor_id[mask].values,
                      "route_stop_id": a.route_stop_id.shift()[mask].values, "gap_start": a.measured_at.shift()[mask].values,
                      "gap_end": a.measured_at[mask].values})
    g["gap_minutes"] = ((g.gap_end - g.gap_start) / np.timedelta64(1, "m")).round().astype(int)
    g["missing_intervals"] = g.gap_minutes // INTERVAL_MIN - 1
    g["exceeds_tolerance"] = (g.gap_minutes > GAP_TOLERANCE_MIN).astype(int)
    g["status"] = "UNVERIFIED"
    return g


def _questionable(rd, cal):
    q = np.zeros(len(rd), bool)
    ts_all = rd.measured_at.values
    cg = {s: g.sort_values("calibrated_at") for s, g in cal[cal.result == "PASS"].groupby("sensor_id")}
    for s, idx in rd.groupby("sensor_id").indices.items():
        c = cg.get(s)
        if c is None:
            q[idx] = True
            continue
        ca, vu, ts = c.calibrated_at.values, c.valid_until.values, ts_all[idx]
        k = np.searchsorted(ca, ts, side="right") - 1
        q[idx] = ~((k >= 0) & (ts < vu[np.clip(k, 0, None)]))
    return q


def monitor(verbose=True) -> dict:
    T = {n: db.read_table(n) for n in db.INPUT_TABLES}
    sh, pol, cal, cus, stops = T["shipments"], T["threshold_policies"], T["sensor_calibrations"], T["custody_events"], T["route_stops"]
    log = print if verbose else (lambda *a, **k: None)

    # ---- 1. reading context + effective-dated policy (policy valid at the READING time, not "latest") ----
    rd = T["sensor_readings"].merge(T["sensors"][["sensor_id", "sensor_type", "container_id"]], on="sensor_id", how="left")
    rd = rd.merge(sh[["shipment_id", "product_id", "container_id"]].rename(columns={"container_id": "ship_container"}), on="shipment_id", how="left")
    rd = rd.sort_values("measured_at", kind="stable").reset_index(drop=True)
    polm = pol.sort_values("effective_from")[["product_id", "policy_id", "effective_from", "effective_to", "min_temperature", "max_temperature",
                                              "min_humidity", "max_humidity", "max_excursion_minutes"]]
    rd = pd.merge_asof(rd, polm, left_on="measured_at", right_on="effective_from", by="product_id", direction="backward")
    rd.loc[rd.effective_to.notna() & (rd.measured_at >= rd.effective_to), "policy_id"] = np.nan
    is_t = (rd.sensor_type == "TEMPERATURE").values
    rd["lo"] = np.where(is_t, rd.min_temperature, rd.min_humidity)
    rd["hi"] = np.where(is_t, rd.max_temperature, rd.max_humidity)
    plo = np.where(is_t, PHYSICAL_RANGE["TEMPERATURE"][0], PHYSICAL_RANGE["HUMIDITY"][0])
    phi = np.where(is_t, PHYSICAL_RANGE["TEMPERATURE"][1], PHYSICAL_RANGE["HUMIDITY"][1])
    v = rd.reading_value.values
    invalid = (v < plo) | (v > phi)
    rd["questionable"] = _questionable(rd, cal)
    late = (rd.received_at - rd.measured_at) > pd.Timedelta(minutes=LATE_ARRIVAL_MIN)
    no_pol = rd.policy_id.isna().values

    # ---- 2. reading flags (original readings are never modified) ----
    def fl(mask, typ, detail):
        return pd.DataFrame({"reading_id": rd.reading_id[mask].values, "flag_type": typ, "detail": detail[mask] if hasattr(detail, "__getitem__") and not isinstance(detail, str) else detail})
    detail_inv = ("value " + rd.reading_value.astype(str) + " outside plausible [" + pd.Series(plo, index=rd.index).astype(str) + ", " + pd.Series(phi, index=rd.index).astype(str) + "]").values
    detail_late = ("arrived " + ((rd.received_at - rd.measured_at).dt.total_seconds() / 60).round().astype(int).astype(str) + " min after measurement").values
    flags = pd.concat([fl(invalid, "PHYSICAL_RANGE_VIOLATION", detail_inv), fl(rd.questionable.values, "CALIBRATION_EXPIRED", "no valid calibration at measurement time"),
                       fl(late.values, "LATE_ARRIVAL", detail_late), fl(no_pol, "NO_APPLICABLE_POLICY", "no policy effective at measurement time")], ignore_index=True)

    # ---- 3. excursions on valid readings ----
    vr = rd[~invalid & ~no_pol].sort_values(["shipment_id", "sensor_id", "measured_at"], kind="stable")
    exc = find_excursions(vr[["shipment_id", "sensor_id", "measured_at", "reading_value", "lo", "hi", "policy_id", "max_excursion_minutes",
                              "sensor_type", "questionable", "route_stop_id"]])
    cu = cus.sort_values("event_time")[["shipment_id", "event_time", "to_party"]]
    exc = pd.merge_asof(exc.sort_values("started_at"), cu, left_on="started_at", right_on="event_time", by="shipment_id", direction="backward")
    exc["responsible_party"] = exc.to_party.fillna("UNKNOWN")
    exc = exc.sort_values(["shipment_id", "started_at", "sensor_id"], kind="stable").reset_index(drop=True)
    exc.insert(0, "excursion_id", [f"EXC-2026-{i+1:06d}" for i in range(len(exc))])
    exc["detected_at"] = exc.ended_at
    log(f"excursions detected: {len(exc)}")

    # ---- 4. monitoring gaps (UNVERIFIED, never safe) ----
    a = rd.sort_values(["shipment_id", "sensor_id", "measured_at"], kind="stable").reset_index(drop=True)
    gaps = find_gaps(a).sort_values(["shipment_id", "sensor_id", "gap_start"], kind="stable").reset_index(drop=True)
    gaps.insert(0, "gap_id", [f"GAP-{i+1:06d}" for i in range(len(gaps))])

    # ---- 5. shipment-level lifecycle / policy / coverage issues ----
    iss = []
    add = lambda df, typ, detail: iss.append(pd.DataFrame({"shipment_id": df.shipment_id.values, "sensor_id": df["sensor_id"].values if "sensor_id" in df else None,
                                                           "issue_type": typ, "detail": detail}))
    dbd = sh[sh.actual_delivery_at < sh.actual_departure_at]
    add(dbd, "DELIVERY_BEFORE_DEPARTURE", ("delivered " + dbd.actual_delivery_at.astype(str) + " before departure " + dbd.actual_departure_at.astype(str)).values)
    shp = sh.sort_values("planned_departure_at")
    shp = pd.merge_asof(shp, polm[["product_id", "policy_id", "effective_from"]].rename(columns={"policy_id": "expected_policy_id"}),
                        left_on="planned_departure_at", right_on="effective_from", by="product_id", direction="backward")
    shp = shp.merge(pol[["policy_id", "product_id"]].rename(columns={"product_id": "policy_product"}), on="policy_id", how="left")
    mm = shp[shp.policy_product != shp.product_id]
    add(mm, "POLICY_MISMATCH", ("assigned " + mm.policy_id + " belongs to " + mm.policy_product.astype(str) + "; expected " + mm.expected_policy_id.astype(str)).values)
    delay = ((sh.actual_delivery_at - sh.planned_arrival_at) / np.timedelta64(1, "m")).round()
    dl = sh[(delay > DELAY_THRESHOLD_MIN) & ~(sh.actual_delivery_at < sh.actual_departure_at)]
    add(dl, "ROUTE_DELAY", ("delivered " + delay[dl.index].astype(int).astype(str) + " min after plan").values)
    nodata = sh[~sh.shipment_id.isin(rd.shipment_id)]
    add(nodata, "NO_MONITORING_DATA", "shipment has no sensor readings (coverage failure)")
    st = stops.sort_values(["shipment_id", "stop_sequence"])
    bad = st[(st.groupby("shipment_id").actual_arrival_at.diff() < pd.Timedelta(0)) | (st.groupby("shipment_id").planned_arrival_at.diff() < pd.Timedelta(0))]
    add(bad.drop_duplicates("shipment_id"), "ROUTE_SEQUENCE_ERROR", "route stop times not in sequence order")
    cs = cus.sort_values(["shipment_id", "event_seq"]).merge(sh[["shipment_id", "actual_departure_at"]], on="shipment_id")
    cbad = cs[(cs.groupby("shipment_id").event_time.diff() < pd.Timedelta(0)) | ((cs.event_seq == 1) & (cs.event_time < cs.actual_departure_at))]
    add(cbad.drop_duplicates("shipment_id"), "CUSTODY_ORDER_ERROR", "custody events out of order or before dispatch")
    sm = rd[rd.container_id != rd.ship_container].groupby(["shipment_id", "sensor_id"]).size().reset_index(name="n")
    add(sm, "READING_SENSOR_MISMATCH", ("readings from a sensor not installed in the shipment container: " + sm.n.astype(str)).values)
    for flag, typ, txt in ((invalid, "PHYSICAL_RANGE_VIOLATION", "physically implausible readings: "), (rd.questionable.values, "CALIBRATION_EXPIRED", "readings without valid calibration: "),
                           (late.values, "LATE_ARRIVAL", "late-arriving readings: ")):
        g = rd[flag].groupby(["shipment_id", "sensor_id"]).size().reset_index(name="n")
        add(g, typ, (txt + g.n.astype(str)).values)
    issues = pd.concat(iss, ignore_index=True).sort_values(["shipment_id", "issue_type", "sensor_id"], na_position="last", kind="stable").reset_index(drop=True)
    issues.insert(0, "issue_id", [f"ISS-{i+1:06d}" for i in range(len(issues))])
    issues["severity"] = issues.issue_type.map(ISSUE_SEV)
    when = sh.set_index("shipment_id")[["actual_departure_at", "actual_delivery_at"]].max(axis=1)
    issues["detected_at"] = issues.shipment_id.map(when)

    # ---- 6. corrective actions + append-only status history ----
    r2 = np.random.default_rng(SEED + 2)
    acts, evs = [], []
    TXT = {"TEMPERATURE": "Inspect refrigeration unit and evaluate product exposure", "HUMIDITY": "Inspect container seal / humidity control and evaluate product exposure"}
    RES = ["Cooling unit serviced; product disposition approved", "Door seal replaced; exposure assessed as acceptable",
           "Sensor and unit verified; batch released with deviation report", "Batch quarantined and escalated to QA"]
    for r in exc[exc.is_actionable == 1].itertuples():
        todo = [("QUALITY_ENGINEER", TXT[r.excursion_type], "HIGH" if r.severity == "HIGH" else "MEDIUM")]
        if r.severity == "HIGH":
            todo.append(("MAINTENANCE_ENGINEER", "Maintenance check of cooling/sensor hardware on container", "HIGH"))
        for role, text, prio in todo:
            aid = f"ACT-{len(acts)+1:06d}"
            final = int(r2.choice(5, p=[.10, .10, .15, .15, .50]))
            t = r.ended_at + pd.Timedelta(minutes=10)
            for s in range(final + 1):
                if s:
                    t += pd.Timedelta(hours=int(r2.integers(1, 13)))
                evs.append(dict(event_id=f"ACE-{len(evs)+1:06d}", action_id=aid, previous_status=ACTION_FLOW[s - 1] if s else None, new_status=ACTION_FLOW[s],
                                changed_by="SYSTEM" if s == 0 else ("QUALITY_ENGINEER" if s in (1, 4) else role), changed_at=t,
                                reason="Auto-created from actionable excursion" if s == 0 else f"{ACTION_FLOW[s-1]} -> {ACTION_FLOW[s]}"))
            acts.append(dict(action_id=aid, excursion_id=r.excursion_id, assigned_role=role, action_description=text, priority=prio, status=ACTION_FLOW[final],
                             created_at=r.ended_at + pd.Timedelta(minutes=10), due_at=r.ended_at + pd.Timedelta(hours=24 if prio == "HIGH" else 48),
                             resolution_text=RES[int(r2.integers(len(RES)))] if final >= 3 else None, last_updated_at=t))
    acts_df = pd.DataFrame(acts, columns=["action_id", "excursion_id", "assigned_role", "action_description", "priority", "status", "created_at", "due_at", "resolution_text", "last_updated_at"])
    evs_df = pd.DataFrame(evs, columns=["event_id", "action_id", "previous_status", "new_status", "changed_by", "changed_at", "reason"])
    by_exc = acts_df.groupby("excursion_id").status.agg(list).to_dict()
    exc["status"] = [("CLOSED" if not r.is_actionable else ("CLOSED" if all(s == "VERIFIED" for s in by_exc[r.excursion_id])
                      else ("OPEN" if all(s == "OPEN" for s in by_exc[r.excursion_id]) else "UNDER_INVESTIGATION"))) for r in exc.itertuples()]

    # ---- 7. notifications (a notification informs; a corrective action records what was done) ----
    r1 = np.random.default_rng(SEED + 1)
    nt = []
    def note(sid, typ, sev, role, msg, created, **fk):
        nt.append(dict(shipment_id=sid, excursion_id=fk.get("e"), gap_id=fk.get("g"), issue_id=fk.get("i"), notification_type=typ, severity=sev, recipient_role=role,
                       message=msg[:400], created_at=created))
    for r in exc.itertuples():
        msg = (f"{r.excursion_type} excursion {r.direction}: {r.shipment_id} peak {r.peak_value:g} vs limit {r.limit_value:g}, {r.duration_minutes} min "
               f"(permissible {r.max_permissible_minutes}); custody: {r.responsible_party}")
        note(r.shipment_id, "EXCURSION_ACTIONABLE" if r.is_actionable else "EXCURSION_PERMISSIBLE", r.severity, "QUALITY_ENGINEER" if r.is_actionable else "PLANT_OPERATOR", msg, r.detected_at, e=r.excursion_id)
        if r.severity == "HIGH":
            note(r.shipment_id, "EXCURSION_ACTIONABLE", "HIGH", "MAINTENANCE_ENGINEER", msg, r.detected_at, e=r.excursion_id)
    for r in gaps[gaps.exceeds_tolerance == 1].itertuples():
        note(r.shipment_id, "MONITORING_GAP", "MEDIUM", "MAINTENANCE_ENGINEER", f"{r.sensor_id}: {r.missing_intervals} readings missing ({r.gap_minutes} min) - condition UNVERIFIED", r.gap_end, g=r.gap_id)
    for r in issues.itertuples():
        note(r.shipment_id, r.issue_type, r.severity, ISSUE_ROLE[r.issue_type], f"{r.issue_type}: {r.detail}", r.detected_at, i=r.issue_id)
    notes = pd.DataFrame(nt).sort_values(["created_at", "shipment_id"], kind="stable").reset_index(drop=True)
    notes.insert(0, "notification_id", [f"NTF-{i+1:06d}" for i in range(len(notes))])
    ack = r1.random(len(notes)) < 0.7
    notes["status"] = np.where(ack, "ACKNOWLEDGED", "SENT")
    notes["acknowledged_at"] = pd.Series(notes.created_at + pd.to_timedelta(r1.integers(5, 240, len(notes)), unit="m")).where(ack, pd.NaT)

    # ---- 8. shipment summary ----
    s = sh[["shipment_id", "product_id", "status"]].copy()
    cnt = lambda df, col=None: df.groupby("shipment_id").size()
    s["excursion_count"] = s.shipment_id.map(cnt(exc)).fillna(0).astype(int)
    s["actionable_excursions"] = s.shipment_id.map(cnt(exc[exc.is_actionable == 1])).fillna(0).astype(int)
    s["gap_count"] = s.shipment_id.map(cnt(gaps)).fillna(0).astype(int)
    s["gaps_over_tolerance"] = s.shipment_id.map(cnt(gaps[gaps.exceeds_tolerance == 1])).fillna(0).astype(int)
    s["unverified_minutes"] = s.shipment_id.map(gaps.groupby("shipment_id").missing_intervals.sum() * INTERVAL_MIN).fillna(0).astype(int)
    s["questionable_readings"] = s.shipment_id.map(rd[rd.questionable.values].groupby("shipment_id").size()).fillna(0).astype(int)
    s["invalid_readings"] = s.shipment_id.map(rd[invalid].groupby("shipment_id").size()).fillna(0).astype(int)
    s["issue_count"] = s.shipment_id.map(cnt(issues)).fillna(0).astype(int)
    s["delay_minutes"] = s.shipment_id.map(delay.set_axis(sh.shipment_id)).where(~s.shipment_id.isin(dbd.shipment_id))
    s["delay_minutes"] = s.delay_minutes.astype("Int64")
    rec_err = s.shipment_id.isin(issues[issues.issue_type.isin(RECORD_ERRORS)].shipment_id)
    nd = s.shipment_id.isin(nodata.shipment_id)
    s["compliance_status"] = np.select(
        [rec_err, s.actionable_excursions > 0, (s.gaps_over_tolerance > 0) | nd, s.excursion_count > 0, (s.questionable_readings > 0) | (s.invalid_readings > 0)],
        ["RECORD_ERROR", "EXCURSION_ACTIONABLE", "UNVERIFIED", "PERMISSIBLE_EXCURSION", "DATA_QUALITY_ISSUE"], "COMPLIANT")
    s = s[["shipment_id", "product_id", "status", "compliance_status", "excursion_count", "actionable_excursions", "gap_count", "gaps_over_tolerance",
           "unverified_minutes", "questionable_readings", "invalid_readings", "issue_count", "delay_minutes"]]

    # ---- 9. persist (derived tables are rebuilt each run; input tables untouched) ----
    exc_out = exc[["excursion_id", "shipment_id", "sensor_id", "policy_id", "route_stop_id", "excursion_type", "direction", "started_at", "ended_at", "end_reason",
                   "duration_minutes", "peak_value", "limit_value", "max_permissible_minutes", "reading_count", "has_internal_gap", "data_quality", "is_actionable",
                   "severity", "status", "responsible_party", "detected_at"]]
    out = dict(reading_flags=flags, monitoring_gaps=gaps[["gap_id", "shipment_id", "sensor_id", "route_stop_id", "gap_start", "gap_end", "gap_minutes", "missing_intervals", "exceeds_tolerance", "status"]],
               excursions=exc_out, shipment_issues=issues[["issue_id", "shipment_id", "sensor_id", "issue_type", "severity", "detail", "detected_at"]],
               notifications=notes[["notification_id", "shipment_id", "excursion_id", "gap_id", "issue_id", "notification_type", "severity", "recipient_role", "message", "created_at", "status", "acknowledged_at"]],
               corrective_actions=acts_df, corrective_action_events=evs_df, shipment_summary=s)
    for t in reversed(db.DERIVED_TABLES):
        db.execute(f"DELETE FROM {t}")
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    for t in db.DERIVED_TABLES:
        db.write_df(t, out[t])
        out[t].to_csv(DERIVED_DIR / f"{t}.csv", index=False, lineterminator="\n")
        log(f"  {t:26s} {len(out[t]):>8,d} rows")
    return out
