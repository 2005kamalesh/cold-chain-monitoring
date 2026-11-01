"""Generate docs/data_dictionary.md from the live schema (types, nullability, PK/FK) plus documented rules."""
import re
from pathlib import Path

from .config import DOCS_DIR

RULES = {
    "reading_value": "float; physical range -50..60 C / 0..100 %RH (plausibility) - outside => INVALID, preserved, excluded",
    "measured_at": "datetime; 5-minute grid within the journey; unique per sensor", "received_at": "datetime >= measured_at; late if > 30 min",
    "min_temperature": "C; < max_temperature", "max_temperature": "C; > min_temperature", "min_humidity": "%RH; < max_humidity", "max_humidity": "%RH; > min_humidity",
    "max_excursion_minutes": "minutes; CONSECUTIVE permissible duration; action only if duration > value", "effective_from": "inclusive start of policy validity",
    "effective_to": "exclusive end; NULL = open-ended", "status": "enum (see business_rules.md lifecycle section)", "duration_minutes": "(ended_at - started_at) in minutes; never count*5",
    "is_actionable": "1 iff duration_minutes > max_permissible_minutes", "severity": "LOW (<= permissible) / MEDIUM (<= 2x) / HIGH (> 2x)",
    "valid_until": "calibration valid while calibrated_at <= t < valid_until", "missing_intervals": "gap_minutes/5 - 1", "exceeds_tolerance": "1 iff gap_minutes > 15",
    "end_reason": "RECOVERED / DIRECTION_CHANGE / END_OF_DATA", "data_quality": "QUESTIONABLE if any reading in the excursion lacked valid calibration",
    "actual_delivery_at": "must be >= actual_departure_at (violations are flagged DELIVERY_BEFORE_DEPARTURE, never silently fixed)",
    "policy_id": "FK; policy's product must equal the shipment's product (else POLICY_MISMATCH)", "event_time": "custody events strictly ordered by event_seq",
}
UNITS = {"temperature": "C", "humidity": "%RH", "minutes": "min", "capacity_kg": "kg", "peak_value": "C or %RH", "limit_value": "C or %RH", "reading_value": "C or %RH"}


def write_data_dictionary():
    ddl = (Path(__file__).parent / "schema.sql").read_text()
    out = ["# Data dictionary", "", "Generated from `coldchain/schema.sql`. PK = primary key, FK = foreign key.", ""]
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", ddl, re.S):
        out += [f"## {name}", "", "| Field | Type | Required | Key | Unit | Validation / rule |", "|---|---|---|---|---|---|"]
        fks = dict(re.findall(r"FOREIGN KEY \((\w+)\) REFERENCES (\w+)\(", body))
        composite = re.findall(r"PRIMARY KEY \(([^)]*)\)", body)
        uniq = re.findall(r"UNIQUE \(([^)]*)\)", body)
        for line in body.splitlines():
            m = re.match(r"\s+(\w+) ([A-Z]+(?:\(\d+\))?)(.*?),?$", line)
            if not m or m.group(1) in ("PRIMARY", "UNIQUE", "FOREIGN", "CHECK"):
                continue
            col, typ, rest = m.groups()
            key = "PK" if "PRIMARY KEY" in rest or (composite and col in composite[0]) else (f"FK -> {fks[col]}" if col in fks else ("UNIQUE" if "UNIQUE" in rest else ""))
            unit = next((u for k, u in UNITS.items() if k in col), "")
            rule = RULES.get(col, "")
            if col.endswith("_id") and key == "PK":
                rule = "immutable deterministic ID (see README nomenclature)"
            elif col != "policy_id" and col in ("policy_id",):
                rule = ""
            if col == "policy_id" and key.startswith("FK"):
                rule = RULES["policy_id"]
            out.append(f"| {col} | {typ} | {'Yes' if 'NOT NULL' in rest or 'PRIMARY KEY' in rest else 'Optional'} | {key} | {unit} | {rule} |")
        if uniq:
            out += ["", "Composite unique: " + "; ".join(f"({u})" for u in uniq)]
        out.append("")
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "data_dictionary.md").write_text("\n".join(out))
    print("wrote docs/data_dictionary.md")
