"""Query/command layer used by the FastAPI app (kept framework-free so it can be unit-tested)."""
import json
from datetime import datetime

import pandas as pd

from . import db
from .config import DOCS_DIR
from .validate import NEXT

OPEN_STATES = ("OPEN", "ASSIGNED", "IN_PROGRESS")


def _records(df: pd.DataFrame) -> list:
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return d.astype(object).where(d.notna(), None).to_dict("records")


def q(sql, params=()):
    return _records(db.query_df(sql, params))


def _where(filters: dict):
    parts = [(f"{k} = ?", v) for k, v in filters.items() if v is not None]
    return (" WHERE " + " AND ".join(p for p, _ in parts) if parts else ""), [v for _, v in parts]


def summary() -> dict:
    s, ex = db.read_table("shipment_summary"), db.read_table("excursions")
    gp, ca, iss = db.read_table("monitoring_gaps"), db.read_table("corrective_actions"), db.read_table("shipment_issues")
    cnt = lambda t: int((iss.issue_type == t).sum())
    return dict(
        total_shipments=len(s), delivered_shipments=int((s.status == "DELIVERED").sum()),
        normal_shipments=int((s.compliance_status == "COMPLIANT").sum()), by_compliance=s.compliance_status.value_counts().to_dict(),
        excursion_count=len(ex), temperature_excursions=int((ex.excursion_type == "TEMPERATURE").sum()), humidity_excursions=int((ex.excursion_type == "HUMIDITY").sum()),
        actionable_excursions=int(ex.is_actionable.sum()), by_severity=ex.severity.value_counts().to_dict(), by_excursion_status=ex.status.value_counts().to_dict(),
        avg_excursion_minutes=round(float(ex.duration_minutes.mean()), 1) if len(ex) else 0, max_excursion_minutes=int(ex.duration_minutes.max()) if len(ex) else 0,
        sensor_dropout_count=len(gp), gaps_over_tolerance=int(gp.exceeds_tolerance.sum()), unverified_minutes=int(gp.missing_intervals.sum() * 5),
        calibration_failure_count=cnt("CALIBRATION_EXPIRED"), invalid_reading_issues=cnt("PHYSICAL_RANGE_VIOLATION"),
        delayed_shipments=cnt("ROUTE_DELAY"), record_errors=int((s.compliance_status == "RECORD_ERROR").sum()),
        open_corrective_actions=int(ca.status.isin(OPEN_STATES).sum()), corrective_actions_by_status=ca.status.value_counts().to_dict())


def list_shipments(compliance_status=None, limit=1000):
    w, p = _where({"m.compliance_status": compliance_status})
    return q("SELECT h.shipment_id, h.origin, h.destination, h.status, h.actual_departure_at, h.actual_delivery_at, h.container_id, h.carrier, "
             "pr.product_name, m.compliance_status, m.excursion_count, m.actionable_excursions, m.gap_count, m.delay_minutes "
             f"FROM shipments h JOIN products pr ON pr.product_id=h.product_id JOIN shipment_summary m ON m.shipment_id=h.shipment_id{w} "
             "ORDER BY h.shipment_id LIMIT ?", p + [limit])


def shipment_detail(sid):
    sh = q("SELECT h.*, pr.product_name FROM shipments h JOIN products pr ON pr.product_id=h.product_id WHERE h.shipment_id=?", (sid,))
    if not sh:
        raise LookupError(f"shipment {sid} not found")
    pid = sh[0]["product_id"]
    return dict(shipment=sh[0], summary=q("SELECT * FROM shipment_summary WHERE shipment_id=?", (sid,))[0],
                policies=q("SELECT * FROM threshold_policies WHERE product_id=? ORDER BY version", (pid,)),
                route_stops=q("SELECT * FROM route_stops WHERE shipment_id=? ORDER BY stop_sequence", (sid,)),
                custody=q("SELECT * FROM custody_events WHERE shipment_id=? ORDER BY event_seq", (sid,)),
                excursions=q("SELECT * FROM excursions WHERE shipment_id=? ORDER BY started_at", (sid,)),
                gaps=q("SELECT * FROM monitoring_gaps WHERE shipment_id=? ORDER BY gap_start", (sid,)),
                issues=q("SELECT * FROM shipment_issues WHERE shipment_id=? ORDER BY issue_id", (sid,)))


def readings(sid):
    r = db.query_df("SELECT r.reading_id, r.sensor_id, s.sensor_type, r.measured_at, r.reading_value, r.route_stop_id FROM sensor_readings r "
                    "JOIN sensors s ON s.sensor_id=r.sensor_id WHERE r.shipment_id=? ORDER BY r.measured_at", (sid,))
    f = db.query_df("SELECT f.reading_id, f.flag_type FROM reading_flags f JOIN sensor_readings r ON r.reading_id=f.reading_id WHERE r.shipment_id=?", (sid,))
    fm = f.groupby("reading_id").flag_type.agg(lambda x: "|".join(x)).to_dict() if len(f) else {}
    r["flags"] = r.reading_id.map(fm).fillna("")
    return _records(r)


def sensors():
    return q("SELECT s.sensor_id, s.container_id, s.sensor_type, s.status, "
             "(SELECT MAX(c.valid_until) FROM sensor_calibrations c WHERE c.sensor_id=s.sensor_id) AS latest_calibration_valid_until, "
             "(SELECT MAX(r.measured_at) FROM sensor_readings r WHERE r.sensor_id=s.sensor_id) AS last_reading_at, "
             "(SELECT COUNT(*) FROM monitoring_gaps g WHERE g.sensor_id=s.sensor_id) AS gap_count "
             "FROM sensors s ORDER BY s.sensor_id")


def excursions(severity=None, excursion_type=None, status=None, shipment_id=None, limit=2000):
    w, p = _where({"severity": severity, "excursion_type": excursion_type, "status": status, "shipment_id": shipment_id})
    return q(f"SELECT * FROM excursions{w} ORDER BY started_at DESC LIMIT ?", p + [limit])


def gaps(exceeds_tolerance=None, limit=2000):
    w, p = _where({"exceeds_tolerance": exceeds_tolerance})
    return q(f"SELECT * FROM monitoring_gaps{w} ORDER BY gap_start DESC LIMIT ?", p + [limit])


def issues(issue_type=None, limit=2000):
    w, p = _where({"issue_type": issue_type})
    return q(f"SELECT * FROM shipment_issues{w} ORDER BY issue_id LIMIT ?", p + [limit])


def notifications(recipient_role=None, limit=2000):
    w, p = _where({"recipient_role": recipient_role})
    return q(f"SELECT * FROM notifications{w} ORDER BY created_at DESC LIMIT ?", p + [limit])


def corrective_actions(status=None, excursion_id=None, limit=2000):
    w, p = _where({"status": status, "excursion_id": excursion_id})
    return q(f"SELECT * FROM corrective_actions{w} ORDER BY created_at DESC LIMIT ?", p + [limit])


def action_history(action_id):
    return q("SELECT * FROM corrective_action_events WHERE action_id=? ORDER BY changed_at, event_id", (action_id,))


def evaluation():
    p = DOCS_DIR / "evaluation_report.json"
    if not p.exists():
        raise LookupError("run `python run.py evaluate` first")
    return json.loads(p.read_text())


# ------------------------------------------------------------------ commands (append history, never overwrite)
def _next_id(cur, table, col, prefix):
    cur.execute(f"SELECT {col} FROM {table} ORDER BY {col} DESC LIMIT 1")
    r = cur.fetchone()
    return f"{prefix}-{(int(r[0].split('-')[-1]) if r else 0) + 1:06d}"


def _sync_excursion_status(cur, excursion_id):
    cur.execute(f"SELECT status FROM corrective_actions WHERE excursion_id={db.PH}", (excursion_id,))
    st = [r[0] for r in cur.fetchall()]
    new = "CLOSED" if st and all(s == "VERIFIED" for s in st) else ("OPEN" if all(s == "OPEN" for s in st) else "UNDER_INVESTIGATION")
    cur.execute(f"UPDATE excursions SET status={db.PH} WHERE excursion_id={db.PH}", (new, excursion_id))


def create_action(excursion_id, assigned_role, description, priority="MEDIUM", due_at=None, created_by="API"):
    now = datetime.now().replace(microsecond=0)
    con = db.connect()
    try:
        cur = con.cursor()
        cur.execute(f"SELECT excursion_id FROM excursions WHERE excursion_id={db.PH}", (excursion_id,))
        if cur.fetchone() is None:
            raise LookupError(f"excursion {excursion_id} not found")
        aid = _next_id(cur, "corrective_actions", "action_id", "ACT")
        eid = _next_id(cur, "corrective_action_events", "event_id", "ACE")
        due = due_at or (now + pd.Timedelta(hours=24 if priority == "HIGH" else 48)).strftime("%Y-%m-%d %H:%M:%S")
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(f"INSERT INTO corrective_actions (action_id, excursion_id, assigned_role, action_description, priority, status, created_at, due_at, resolution_text, last_updated_at) "
                    f"VALUES ({','.join([db.PH] * 10)})", (aid, excursion_id, assigned_role, description, priority, "OPEN", ts, due, None, ts))
        cur.execute(f"INSERT INTO corrective_action_events (event_id, action_id, previous_status, new_status, changed_by, changed_at, reason) VALUES ({','.join([db.PH] * 7)})",
                    (eid, aid, None, "OPEN", created_by, ts, "Created manually"))
        _sync_excursion_status(cur, excursion_id)
        con.commit()
    finally:
        con.close()
    return q("SELECT * FROM corrective_actions WHERE action_id=?", (aid,))[0]


def advance_action(action_id, new_status, changed_by, reason=None, resolution_text=None):
    now = datetime.now().replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    con = db.connect()
    try:
        cur = con.cursor()
        cur.execute(f"SELECT status, excursion_id FROM corrective_actions WHERE action_id={db.PH}", (action_id,))
        row = cur.fetchone()
        if row is None:
            raise LookupError(f"action {action_id} not found")
        cur_status, exc_id = row
        if NEXT.get(cur_status) != new_status:
            raise ValueError(f"invalid transition {cur_status} -> {new_status}; the only allowed next status is {NEXT.get(cur_status)}")
        if new_status == "RESOLVED" and not resolution_text:
            raise ValueError("resolution_text is required when resolving an action")
        eid = _next_id(cur, "corrective_action_events", "event_id", "ACE")
        cur.execute(f"INSERT INTO corrective_action_events (event_id, action_id, previous_status, new_status, changed_by, changed_at, reason) VALUES ({','.join([db.PH] * 7)})",
                    (eid, action_id, cur_status, new_status, changed_by, now, reason or f"{cur_status} -> {new_status}"))
        cur.execute(f"UPDATE corrective_actions SET status={db.PH}, last_updated_at={db.PH}, resolution_text=COALESCE({db.PH}, resolution_text) WHERE action_id={db.PH}",
                    (new_status, now, resolution_text, action_id))
        _sync_excursion_status(cur, exc_id)
        con.commit()
    finally:
        con.close()
    return q("SELECT * FROM corrective_actions WHERE action_id=?", (action_id,))[0]
