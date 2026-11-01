"""Synthetic data generator (seeded, deterministic, scale-parameterised).

Order: master data -> shipments/containers/route -> readings -> labelled anomaly injection -> custody -> ground truth.
Expected results in ground_truth.csv are derived from the *injection parameters + documented rules*, never from the
monitoring engine. The engine never reads the ground truth.
"""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .config import SEED, RAW_DIR, GT_DIR, GAP_TOLERANCE_MIN, DELAY_THRESHOLD_MIN

# name, category, tmin, tmax, hmin, hmax, permissible excursion minutes (policy v1) -- illustrative values only
PRODUCTS = [
    ("Vaccine A", "Vaccine", 2, 8, 30, 60, 15),
    ("Insulin B", "Biologic", 2, 8, 30, 65, 20),
    ("Frozen Biologic C", "Frozen Biologic", -25, -15, 20, 50, 10),
    ("Tablets D", "Controlled Room Temp", 15, 25, 30, 60, 60),
    ("Dairy Product E", "Dairy", 1, 6, 40, 80, 30),
    ("Diagnostic Reagent F", "Reagent", 2, 8, 30, 60, 20),
]
POLICY_V2_FROM = datetime(2026, 9, 15)       # policy v2 shortens the permissible duration by 5 min
START = datetime(2026, 7, 1)
CARRIERS = ["Carrier Alpha Logistics", "Carrier Beta Freight", "Carrier Gamma Cold Chain", "Carrier Delta Transport"]
LANES = [["Hyderabad", "Kurnool", "Anantapur", "Bangalore"], ["Delhi", "Jaipur", "Ahmedabad", "Mumbai"],
         ["Chennai", "Vijayawada", "Visakhapatnam", "Kolkata"], ["Mumbai", "Pune", "Solapur", "Hyderabad"],
         ["Bangalore", "Salem", "Madurai", "Chennai"]]
CONTAINER_TYPES = ["REEFER_TRUCK", "INSULATED_BOX", "PALLET_SHIPPER", "REEFER_CONTAINER"]
SCENARIOS = [("NORMAL", .60), ("BRIEF", .12), ("PROLONGED", .10), ("DROPOUT", .07), ("CALIBRATION", .04),
             ("ROUTE_DELAY", .04), ("MULTI", .03)]
MULTI_POOL = ["BRIEF", "PROLONGED", "DROPOUT", "CALIBRATION", "ROUTE_DELAY"]
GT_COLS = ["scenario_id", "shipment_id", "sensor_id", "reading_id", "issue_type", "injected_scenario",
           "expected_detection", "expected_start", "expected_end", "expected_duration_minutes",
           "expected_missing_intervals", "expected_actionable", "expected_severity", "expected_value",
           "expected_count", "notes"]


def expected_severity(duration, perm):  # independent copy of the documented rule
    return "LOW" if duration <= perm else ("MEDIUM" if duration <= 2 * perm else "HIGH")


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def baseline(rng, n, lo, hi, dec):
    span, t = hi - lo, np.arange(n)
    v = (lo + hi) / 2 + 0.12 * span * np.sin(2 * np.pi * t / 288 + rng.uniform(0, 6.28)) + rng.normal(0, 0.07 * span, n)
    return np.round(np.clip(v, lo + 0.08 * span, hi - 0.08 * span), dec)


def generate(n_shipments=100, n_containers=30, seed=SEED, out_dir=RAW_DIR, gt_dir=GT_DIR):
    out_dir, gt_dir = Path(out_dir), Path(gt_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    N = n_shipments
    M5 = lambda x: timedelta(minutes=int(x))

    # ---------------- master data ----------------
    products, policies, pol_by = [], [], {}
    for i, (nm, cat, tmin, tmax, hmin, hmax, dur) in enumerate(PRODUCTS, 1):
        pid = f"PRD-{i:06d}"
        products.append(dict(product_id=pid, product_name=nm, category=cat, storage_class=f"{tmin:g} to {tmax:g} C",
                             created_at=datetime(2026, 1, 1)))
        base = dict(product_id=pid, min_temperature=tmin, max_temperature=tmax, min_humidity=hmin, max_humidity=hmax)
        p1 = dict(policy_id=f"POL-{2*i-1:06d}", version=1, max_excursion_minutes=dur, effective_from=datetime(2026, 1, 1),
                  effective_to=POLICY_V2_FROM, status="SUPERSEDED", **base)
        p2 = dict(policy_id=f"POL-{2*i:06d}", version=2, max_excursion_minutes=max(5, dur - 5), effective_from=POLICY_V2_FROM,
                  effective_to=None, status="ACTIVE", **base)
        policies += [p1, p2]
        pol_by[pid] = [p1, p2]

    def policy_at(pid, t):
        return next(p for p in pol_by[pid] if p["effective_from"] <= t and (p["effective_to"] is None or t < p["effective_to"]))

    containers, sensors, chains = [], [], {}
    for c in range(1, n_containers + 1):
        cid = f"CNT-{c:06d}"
        containers.append(dict(container_id=cid, container_type=CONTAINER_TYPES[int(rng.integers(4))],
                               capacity_kg=int(rng.integers(5, 40)) * 100, status="ACTIVE"))
        for typ, suf, unit, model in (("TEMPERATURE", "TEMP", "C", "ThermoLog T100"), ("HUMIDITY", "HUM", "%RH", "HygroLog H200")):
            sid_ = f"SNS-{cid}-{suf}"
            sensors.append(dict(sensor_id=sid_, container_id=cid, sensor_type=typ, unit=unit, model=model, status="ACTIVE",
                                installed_at=datetime(2026, 3, 1)))
            starts = [datetime(2026, 4, 15) + timedelta(days=60 * k) for k in range(5)]
            chains[sid_] = [[s, s + timedelta(days=60)] for s in starts]

    # ---------------- scenario plan ----------------
    counts = {k: int(N * w) for k, w in SCENARIOS}
    counts["NORMAL"] += N - sum(counts.values())
    scen = rng.permutation(np.array([k for k, c in counts.items() for _ in range(c)])).tolist()
    normal = rng.permutation([i for i, s in enumerate(scen) if s == "NORMAL"]).tolist()
    take = lambda n: [normal.pop() for _ in range(min(n, len(normal)))]
    E_PHYS, E_DBD, E_MIS = set(take(max(2, round(N * .012)))), set(take(max(1, round(N * .008)))), set(take(max(1, round(N * .008))))
    E_TRAP, E_BND = set(take(max(1, round(N * .01)))), set(take(max(2, round(N * .01))))
    window_days = max(60, int(N * 0.11))
    offsets = np.sort(rng.integers(0, window_days * 288, N))
    free_at = np.full(n_containers, np.datetime64("2000-01-01"), dtype="datetime64[s]")

    shipments, stops_rows, custody, gt, scen_rows = [], [], [], [], []
    asg_rows, sse_rows = [], []
    kept, late_counts, buf = {}, {}, []
    rd_path = out_dir / "sensor_readings.csv"
    first_chunk, cus_n = True, 0

    def flush():
        nonlocal first_chunk, buf
        if buf:
            pd.concat(buf).to_csv(rd_path, mode="w" if first_chunk else "a", header=first_chunk, index=False, lineterminator="\n")
            first_chunk, buf = False, []

    for i in range(N):
        sid = f"SHP-2026-{i+1:06d}"
        sc = scen[i]
        comps = [] if sc == "NORMAL" else ([sc] if sc != "MULTI" else rng.choice(MULTI_POOL, size=int(rng.integers(2, 4)), replace=False).tolist())
        pidx = int(rng.integers(len(PRODUCTS)))
        pid = f"PRD-{pidx+1:06d}"
        _, _, tmin, tmax, hmin, hmax, _ = PRODUCTS[pidx]
        D = int(rng.integers(576, 1441)) * 5  # 2-5 days in minutes
        lane = LANES[int(rng.integers(len(LANES)))]
        locs = [lane[0]] + lane[1:-1][:int(rng.integers(1, 3))] + [lane[-1]]
        m = len(locs)

        P = START + M5(offsets[i] * 5)
        cand = np.where(free_at + np.timedelta64(12, "h") <= np.datetime64(P, "s"))[0]
        if len(cand) == 0:  # no free container: hold departure until the earliest container is released + 12 h
            c = int(np.argmin(free_at))
            P = pd.Timestamp(free_at[c] + np.timedelta64(12, "h")).to_pydatetime()
        else:
            c = int(rng.choice(cand))
        cid = f"CNT-{c+1:06d}"
        dep0 = P + M5(5 * int(rng.integers(0, 3)))
        delay, delay_from = 0, m
        if "ROUTE_DELAY" in comps:
            delay, delay_from = 5 * int(rng.integers(48, 169)), int(rng.integers(1, m))

        p_arr, p_dep, a_arr, a_dep = [P - M5(30)], [P], [dep0 - M5(30)], [dep0]
        for j in range(1, m):
            off = M5(5 * round(D * j / (m - 1) / 5))
            p_arr.append(P + off)
            a_arr.append(dep0 + off + M5(5 * int(rng.integers(-3, 6)) + (delay if j >= delay_from else 0)))
            last = j == m - 1
            p_dep.append(None if last else p_arr[-1] + M5(30))
            a_dep.append(None if last else a_arr[-1] + M5(30))
        delivery, planned_arrival = a_arr[-1], p_arr[-1]
        stop_ids = [f"RST-{sid}-{j+1:02d}" for j in range(m)]
        for j in range(m):
            stops_rows.append(dict(route_stop_id=stop_ids[j], shipment_id=sid, stop_sequence=j + 1, location=locs[j],
                                   stop_type="ORIGIN" if j == 0 else ("DESTINATION" if j == m - 1 else "TRANSIT_HUB"),
                                   planned_arrival_at=p_arr[j], planned_departure_at=p_dep[j],
                                   actual_arrival_at=a_arr[j], actual_departure_at=a_dep[j]))
        carrier = CARRIERS[int(rng.integers(len(CARRIERS)))]
        ev = [("DISPATCH_HANDOVER", f"{locs[0]} Warehouse", carrier, 0, dep0)]
        for j in range(1, m - 1):
            ev += [("HUB_RECEIPT", carrier, f"{locs[j]} Hub", j, a_arr[j]), ("HUB_RELEASE", f"{locs[j]} Hub", carrier, j, a_dep[j])]
        ev.append(("DELIVERY_HANDOVER", carrier, f"{locs[-1]} Warehouse", m - 1, delivery))
        for seq, (et, fp, tp, j, tm) in enumerate(ev, 1):
            cus_n += 1
            custody.append(dict(custody_event_id=f"CUS-{cus_n:06d}", shipment_id=sid, route_stop_id=stop_ids[j], event_seq=seq,
                                event_type=et, from_party=fp, to_party=tp, location=locs[j], event_time=tm))

        # policy assigned at shipment creation (deliberately wrong for E_MIS shipments)
        pol = policy_at(pid, P)
        assigned = pol["policy_id"]
        if i in E_MIS:
            oth = f"PRD-{(pidx + int(rng.integers(1, len(PRODUCTS)))) % len(PRODUCTS) + 1:06d}"  # always a DIFFERENT product
            assigned = policy_at(oth, P)["policy_id"]
            gt.append(dict(shipment_id=sid, issue_type="POLICY_MISMATCH", injected_scenario="EDGE_POLICY_MISMATCH",
                           expected_detection=True, expected_start=P, notes=f"expected_policy_id={pol['policy_id']}; assigned={assigned}"))

        # ---------------- readings ----------------
        n = int((delivery - dep0).total_seconds() // 300) + 1
        ts = np.datetime64(dep0, "s") + np.arange(n) * np.timedelta64(300, "s")
        st = {"TEMPERATURE": dict(sensor=f"SNS-{cid}-TEMP", unit="C", dec=2, lim=(tmin, tmax)),
              "HUMIDITY": dict(sensor=f"SNS-{cid}-HUM", unit="%RH", dec=1, lim=(hmin, hmax))}
        vals = {k: baseline(rng, n, *v["lim"], v["dec"]) for k, v in st.items()}
        keep = {k: np.ones(n, bool) for k in st}
        late = {k: np.zeros(n, bool) for k in st}
        occ = {k: np.zeros(n, bool) for k in st}
        tsp = lambda x: pd.Timestamp(ts[x]).to_pydatetime()
        rid = lambda k, x: f"RDG-{st[k]['sensor']}-{pd.Timestamp(ts[x]).strftime('%Y%m%dT%H%M%S')}"

        def place(k, length, margin=6):
            for _ in range(60):
                s = int(rng.integers(margin + 6, n - length - margin - 6))
                if not occ[k][s - margin:s + length + margin].any():
                    occ[k][s - margin:s + length + margin] = True
                    return s
            return None

        def inject_exc(k, n_ex, label, gap_inside=0):
            s = place(k, n_ex + 1)
            if s is None:
                return
            lo, hi = st[k]["lim"]
            d = 1 if rng.random() < 0.7 else -1
            delta = rng.uniform(0.4, 3.0, n_ex) if k == "TEMPERATURE" else rng.uniform(2.0, 15.0, n_ex)
            v = np.round(hi + delta if d == 1 else lo - delta, st[k]["dec"])
            vals[k][s:s + n_ex] = v
            peak = float(v.max() if d == 1 else v.min())
            dur = n_ex * 5
            perm = policy_at(pid, tsp(s))["max_excursion_minutes"]
            gt.append(dict(shipment_id=sid, sensor_id=st[k]["sensor"], issue_type=f"{k}_EXCURSION", injected_scenario=label,
                           expected_detection=True, expected_start=tsp(s), expected_end=tsp(s + n_ex), expected_duration_minutes=dur,
                           expected_actionable=dur > perm, expected_severity=expected_severity(dur, perm), expected_value=peak,
                           notes=f"permissible_min={perm}; direction={'HIGH' if d == 1 else 'LOW'}"
                                 + (f"; naive_count_duration={(n_ex - gap_inside) * 5}" if gap_inside else "")))
            if gap_inside:
                keep[k][s + 2:s + 2 + gap_inside] = False
                gt.append(dict(shipment_id=sid, sensor_id=st[k]["sensor"], issue_type="MISSING_INTERVAL", injected_scenario=label,
                               expected_detection=True, expected_start=tsp(s + 1), expected_end=tsp(s + 2 + gap_inside),
                               expected_missing_intervals=gap_inside, expected_actionable=(gap_inside + 1) * 5 > GAP_TOLERANCE_MIN))

        def inject_dropout(k, mm, as_late, label):
            s = place(k, mm)
            if s is None:
                return
            if as_late:
                late[k][s:s + mm] = True
            else:
                keep[k][s:s + mm] = False
                gt.append(dict(shipment_id=sid, sensor_id=st[k]["sensor"], issue_type="MISSING_INTERVAL", injected_scenario=label,
                               expected_detection=True, expected_start=tsp(s - 1), expected_end=tsp(s + mm),
                               expected_missing_intervals=mm, expected_actionable=(mm + 1) * 5 > GAP_TOLERANCE_MIN))

        def lapse():
            k = "TEMPERATURE" if rng.random() < 0.5 else "HUMIDITY"
            ch = chains[st[k]["sensor"]]
            rec = next((r for r in ch if r[0] <= dep0 < r[1]), None)
            if rec is None or rec[1] < delivery + timedelta(days=1):
                return
            expire = dep0 + M5(5 * int((delivery - dep0).total_seconds() / 300 * rng.uniform(0.25, 0.6)))
            ch.append([delivery + timedelta(hours=6), rec[1]])
            rec[1] = expire

        for comp in comps:
            if comp in ("BRIEF", "PROLONGED"):
                k = "TEMPERATURE" if rng.random() < 0.75 else "HUMIDITY"
                pm = [p["max_excursion_minutes"] for p in pol_by[pid]]
                n_ex = int(rng.integers(1, min(pm) // 5 + 1)) if comp == "BRIEF" else max(pm) // 5 + int(rng.integers(1, 21))
                inject_exc(k, n_ex, comp)
            elif comp == "DROPOUT":
                for _ in range(int(rng.integers(1, 4))):
                    inject_dropout(list(st)[int(rng.integers(2))], int(rng.integers(2, 25)), rng.random() < 0.25, comp)
            elif comp == "CALIBRATION":
                lapse()
        if i in E_TRAP:
            inject_exc("TEMPERATURE", int(rng.integers(8, 16)), "EXC_WITH_INTERNAL_GAP", gap_inside=int(rng.integers(2, 4)))
        if i in E_BND:
            s = place("TEMPERATURE", 3)
            if s is not None:
                vals["TEMPERATURE"][s:s + 2], vals["TEMPERATURE"][s + 2] = tmax, tmin
                gt.append(dict(shipment_id=sid, sensor_id=st["TEMPERATURE"]["sensor"], issue_type="BOUNDARY_INCLUSIVE",
                               injected_scenario="EDGE_BOUNDARY", expected_detection=False, expected_start=tsp(s), expected_end=tsp(s + 2),
                               notes="readings exactly equal max,max,min limit must NOT create an excursion"))
        if i in E_PHYS:
            for _ in range(int(rng.integers(1, 4))):
                k = list(st)[int(rng.integers(2))]
                s = place(k, 1, margin=3)
                if s is not None:
                    bad = float(rng.choice([150.0, 250.0, -100.0] if k == "TEMPERATURE" else [130.0, 250.0, -20.0]))
                    vals[k][s] = bad
                    gt.append(dict(shipment_id=sid, sensor_id=st[k]["sensor"], reading_id=rid(k, s), issue_type="PHYSICAL_RANGE_VIOLATION",
                                   injected_scenario="EDGE_PHYSICAL_RANGE", expected_detection=True, expected_value=bad))

        for k, v in st.items():  # build reading rows (arrays drawn at full length => deterministic RNG use)
            recv_off = rng.integers(5, 60, n)
            late_off = rng.integers(2100, 5400, n)
            idx = np.where(keep[k])[0]
            tk = ts[idx]
            late_counts[(sid, v["sensor"])] = int(late[k][idx].sum())
            kept[(sid, v["sensor"])] = tk
            sec = np.where(late[k], late_off, recv_off)[idx].astype("timedelta64[s]")
            strs = pd.DatetimeIndex(tk).strftime("%Y%m%dT%H%M%S")
            ridx = np.clip(np.searchsorted(np.array([np.datetime64(x, "s") for x in a_arr]), tk, side="right") - 1, 0, m - 1)
            buf.append(pd.DataFrame(dict(
                reading_id="RDG-" + v["sensor"] + "-" + strs, sensor_id=v["sensor"], shipment_id=sid,
                route_stop_id=np.array(stop_ids)[ridx], measured_at=pd.to_datetime(tk), received_at=pd.to_datetime(tk + sec),
                reading_value=vals[k][idx], unit=v["unit"])))

        recorded = delivery
        if i in E_DBD:
            recorded = dep0 - timedelta(hours=int(rng.integers(5, 49)))
            gt.append(dict(shipment_id=sid, issue_type="DELIVERY_BEFORE_DEPARTURE", injected_scenario="EDGE_DELIVERY_BEFORE_DEPARTURE",
                           expected_detection=True, expected_start=dep0, expected_end=recorded))
        delay_min = int((delivery - planned_arrival).total_seconds() // 60)
        if delay_min > DELAY_THRESHOLD_MIN and i not in E_DBD:
            gt.append(dict(shipment_id=sid, issue_type="ROUTE_DELAY", injected_scenario="ROUTE_DELAY", expected_detection=True,
                           expected_value=delay_min, expected_end=delivery))
        free_at[c] = np.datetime64(delivery, "s")
        shipments.append(dict(shipment_id=sid, product_id=pid, container_id=cid, policy_id=assigned, origin=locs[0], destination=locs[-1],
                              carrier=carrier, planned_departure_at=P, planned_arrival_at=planned_arrival, actual_departure_at=dep0,
                              actual_delivery_at=recorded, status="DELIVERED"))
        for suf in ("TEMP", "HUM"):
            asg_rows.append(dict(assignment_id=f"ASG-{len(asg_rows)+1:06d}", shipment_id=sid, sensor_id=f"SNS-{cid}-{suf}",
                                 assigned_at=P - M5(60), released_at=delivery + M5(30)))
        for prev, new, who, tm in ((None, "CREATED", "Production Planner", P - timedelta(hours=24)), ("CREATED", "DISPATCHED", carrier, dep0),
                                   ("DISPATCHED", "IN_TRANSIT", carrier, dep0 + M5(30)), ("IN_TRANSIT", "DELIVERED", carrier, recorded)):
            sse_rows.append(dict(status_event_id=f"SSE-{len(sse_rows)+1:06d}", shipment_id=sid, previous_status=prev, new_status=new, changed_by=who, changed_at=tm))
        flags = [k for k, s in (("PHYS", E_PHYS), ("DBD", E_DBD), ("MISMATCH", E_MIS), ("TRAP", E_TRAP), ("BOUNDARY", E_BND)) if i in s]
        scen_rows.append(dict(shipment_id=sid, scenario=sc, components="|".join(comps), edge_flags="|".join(flags)))
        if len(buf) >= 50:
            flush()
    flush()

    # calibration chains are final only now -> record them and derive expected CALIBRATION_EXPIRED / LATE_ARRIVAL counts
    cal_rows, cn = [], 0
    for sensor_id in sorted(chains):
        for a, b in sorted(chains[sensor_id]):
            cn += 1
            cal_rows.append(dict(calibration_id=f"CAL-{cn:06d}", sensor_id=sensor_id, calibrated_at=a, valid_until=b, result="PASS"))
    for (sid, sensor_id), tk in kept.items():
        ch = sorted(chains[sensor_id])
        ca = np.array([np.datetime64(a, "s") for a, _ in ch])
        vu = np.array([np.datetime64(b, "s") for _, b in ch])
        k_ = np.searchsorted(ca, tk, side="right") - 1
        bad = int((~((k_ >= 0) & (tk < vu[np.clip(k_, 0, None)]))).sum())
        if bad:
            gt.append(dict(shipment_id=sid, sensor_id=sensor_id, issue_type="CALIBRATION_EXPIRED", injected_scenario="CALIBRATION",
                           expected_detection=True, expected_count=bad))
        if late_counts[(sid, sensor_id)]:
            gt.append(dict(shipment_id=sid, sensor_id=sensor_id, issue_type="LATE_ARRIVAL", injected_scenario="DROPOUT",
                           expected_detection=True, expected_count=late_counts[(sid, sensor_id)]))

    gtdf = pd.DataFrame(gt).reindex(columns=GT_COLS)
    gtdf = gtdf.sort_values(["shipment_id", "issue_type", "sensor_id", "expected_start"], na_position="last", kind="stable").reset_index(drop=True)
    gtdf["scenario_id"] = [f"SCN-{j+1:06d}" for j in range(len(gtdf))]

    def save(df, path):
        df.to_csv(path, index=False, lineterminator="\n")

    tables = dict(products=products, threshold_policies=policies, containers=containers, sensors=sensors,
                  sensor_calibrations=cal_rows, shipments=shipments, shipment_sensor_assignments=asg_rows,
                  shipment_status_events=sse_rows, route_stops=stops_rows, custody_events=custody)
    for name, rows in tables.items():
        save(pd.DataFrame(rows), out_dir / f"{name}.csv")
    save(gtdf, gt_dir / "ground_truth.csv")
    save(pd.DataFrame(scen_rows), gt_dir / "shipment_scenarios.csv")
    files = {p.name: dict(rows=sum(1 for _ in open(p, "rb")) - 1, md5=md5(p)) for p in sorted(list(out_dir.glob("*.csv")) + list(gt_dir.glob("*.csv")))}
    manifest = dict(generator="coldchain.generator", seed=seed, shipments=N, containers=n_containers,
                    external_data="none (fully synthetic; no third-party data used)", files=files)
    (out_dir.parent / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
