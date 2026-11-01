"""Streamlit dashboard (talks to the FastAPI backend).  Run:  streamlit run dashboard.py   (API must be running)"""
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000")
st.set_page_config(page_title="Cold Chain Monitor", layout="wide")


@st.cache_data(ttl=20, show_spinner=False)
def get(path, **params):
    r = requests.get(f"{API}{path}", params={k: v for k, v in params.items() if v not in (None, "ALL")}, timeout=120)
    r.raise_for_status()
    return r.json()


def send(method, path, body):
    r = requests.request(method, f"{API}{path}", json=body, timeout=60)
    if r.status_code >= 400:
        st.error(r.json().get("detail", r.text))
        return None
    get.clear()
    return r.json()


def df(path, **params):
    return pd.DataFrame(get(path, **params))


try:
    S = get("/dashboard/summary")
except Exception as e:
    st.error(f"Cannot reach the API at {API}. Start it with: uvicorn coldchain.api:app\n\n{e}")
    st.stop()

page = st.sidebar.radio("Cold Chain Monitor", ["Overview", "Shipment monitoring", "Excursions", "Corrective actions", "Sensors & data quality", "Detection evaluation"])
st.sidebar.caption("Unverified (missing) data is never treated as compliant.")

# ------------------------------------------------------------------------------------------------ Overview
if page == "Overview":
    st.title("Overview")
    c = st.columns(6)
    c[0].metric("Shipments", S["total_shipments"])
    c[1].metric("Fully compliant", S["normal_shipments"])
    c[2].metric("Excursions", S["excursion_count"], f"{S['actionable_excursions']} actionable", delta_color="off")
    c[3].metric("Monitoring gaps", S["sensor_dropout_count"], f"{S['gaps_over_tolerance']} over tolerance", delta_color="off")
    c[4].metric("Delayed shipments", S["delayed_shipments"])
    c[5].metric("Open corrective actions", S["open_corrective_actions"])
    c = st.columns(5)
    c[0].metric("Temperature excursions", S["temperature_excursions"])
    c[1].metric("Humidity excursions", S["humidity_excursions"])
    c[2].metric("Avg excursion (min)", S["avg_excursion_minutes"])
    c[3].metric("Max excursion (min)", S["max_excursion_minutes"])
    c[4].metric("Calibration failures", S["calibration_failure_count"])
    a, b = st.columns(2)
    comp = pd.DataFrame({"status": list(S["by_compliance"]), "shipments": list(S["by_compliance"].values())})
    a.plotly_chart(px.bar(comp, x="status", y="shipments", color="status", title="Shipments by compliance status"), width='stretch')
    ex = df("/excursions")
    if len(ex):
        b.plotly_chart(px.histogram(ex, x="duration_minutes", color="severity", nbins=30, title="Excursion duration (minutes) by severity"), width='stretch')
    st.caption(f"Shipments with record errors (lifecycle/policy): {S['record_errors']} | Unverified minutes (missing data): {S['unverified_minutes']}")

# ------------------------------------------------------------------------------------------------ Shipment monitoring
elif page == "Shipment monitoring":
    st.title("Shipment monitoring")
    flt = st.selectbox("Compliance filter", ["ALL"] + list(S["by_compliance"]))
    sh = df("/shipments", compliance_status=flt)
    sid = st.selectbox("Shipment", sh.shipment_id.tolist(), format_func=lambda x: f"{x}  -  {sh.set_index('shipment_id').loc[x, 'compliance_status']}")
    D = get(f"/shipments/{sid}")
    s = D["shipment"]
    c = st.columns(5)
    c[0].metric("Product", s["product_name"])
    c[1].metric("Route", f"{s['origin']} -> {s['destination']}")
    c[2].metric("Container", s["container_id"])
    c[3].metric("Compliance", D["summary"]["compliance_status"])
    c[4].metric("Delay (min)", D["summary"]["delay_minutes"] if D["summary"]["delay_minutes"] is not None else "n/a")
    R = df(f"/shipments/{sid}/readings")
    pol = D["policies"][-1]
    for typ, lo, hi, unit in (("TEMPERATURE", pol["min_temperature"], pol["max_temperature"], "°C"), ("HUMIDITY", pol["min_humidity"], pol["max_humidity"], "%RH")):
        r = R[R.sensor_type == typ].copy()
        r["measured_at"] = pd.to_datetime(r.measured_at)
        good = r[~r["flags"].astype(str).str.contains("PHYSICAL_RANGE_VIOLATION")]
        bad = r[r["flags"].astype(str).str.contains("PHYSICAL_RANGE_VIOLATION")]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=good.measured_at, y=good.reading_value, mode="lines", name=typ.title(), connectgaps=False))
        q = good[good["flags"].astype(str).str.contains("CALIBRATION_EXPIRED")]
        if len(q):
            fig.add_trace(go.Scatter(x=q.measured_at, y=q.reading_value, mode="markers", name="Questionable (calibration)", marker=dict(color="orange", size=4)))
        fig.add_hline(y=hi, line_dash="dash", line_color="red", annotation_text=f"max {hi:g}")
        fig.add_hline(y=lo, line_dash="dash", line_color="red", annotation_text=f"min {lo:g}")
        for e in D["excursions"]:
            if e["excursion_type"] == typ:
                fig.add_vrect(x0=e["started_at"], x1=e["ended_at"], fillcolor="red", opacity=0.25, line_width=0, annotation_text=f"{e['severity']} {e['duration_minutes']}m")
        for g in D["gaps"]:
            if g["sensor_id"].endswith("TEMP" if typ == "TEMPERATURE" else "HUM"):
                fig.add_vrect(x0=g["gap_start"], x1=g["gap_end"], fillcolor="grey", opacity=0.35, line_width=0, annotation_text="UNVERIFIED")
        fig.update_layout(title=f"{typ.title()} ({unit}) - red = excursion, grey = unverified gap", height=330, margin=dict(t=50, b=10))
        st.plotly_chart(fig, width='stretch')
        if len(bad):
            st.warning(f"{len(bad)} physically implausible {typ.lower()} reading(s) preserved but excluded from excursion logic: " + ", ".join(f"{v:g}" for v in bad.reading_value))
    t1, t2, t3, t4 = st.tabs(["Excursions", "Monitoring gaps", "Route & custody", "Issues"])
    def show(tab, rows, empty_msg):
        if rows:
            tab.dataframe(pd.DataFrame(rows), width='stretch')
        else:
            tab.info(empty_msg)
    show(t1, D["excursions"], "No excursions: every valid reading stayed within the product limits for this shipment.")
    show(t2, D["gaps"], "No monitoring gaps: readings arrived at every 5-minute interval for this shipment.")
    show(t3, D["route_stops"], "No route stops.")
    if D["custody"]:
        t3.dataframe(pd.DataFrame(D["custody"]), width='stretch')
    show(t4, D["issues"], "No issues: no lifecycle, policy, calibration, delay or data-quality problems for this shipment.")
    if D["summary"]["compliance_status"] == "COMPLIANT":
        st.success("This shipment is fully COMPLIANT, so empty tabs are the correct result. Use the Compliance filter at the top to find shipments with excursions, gaps or issues.")

# ------------------------------------------------------------------------------------------------ Excursions
elif page == "Excursions":
    st.title("Excursion management")
    c = st.columns(3)
    sev = c[0].selectbox("Severity", ["ALL", "HIGH", "MEDIUM", "LOW"])
    typ = c[1].selectbox("Type", ["ALL", "TEMPERATURE", "HUMIDITY"])
    stt = c[2].selectbox("Status", ["ALL", "OPEN", "UNDER_INVESTIGATION", "CLOSED"])
    ex = df("/excursions", severity=sev, excursion_type=typ, status=stt)
    st.caption("LOW = within permissible duration (recorded, no action). MEDIUM/HIGH = actionable (duration > permissible).")
    if len(ex):
        st.dataframe(ex[["excursion_id", "shipment_id", "excursion_type", "direction", "started_at", "ended_at", "duration_minutes", "max_permissible_minutes", "peak_value",
                         "limit_value", "severity", "status", "data_quality", "has_internal_gap", "responsible_party"]], width='stretch')
        st.plotly_chart(px.scatter(ex, x="max_permissible_minutes", y="duration_minutes", color="severity", symbol="excursion_type", hover_name="excursion_id",
                                   title="Duration vs permissible duration"), width='stretch')
    else:
        st.info("No excursions match the filter.")

# ------------------------------------------------------------------------------------------------ Corrective actions
elif page == "Corrective actions":
    st.title("Corrective actions")
    stt = st.selectbox("Status", ["ALL", "OPEN", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "VERIFIED"])
    ca = df("/corrective-actions", status=stt)
    st.dataframe(ca, width='stretch')
    nxt = {"OPEN": "ASSIGNED", "ASSIGNED": "IN_PROGRESS", "IN_PROGRESS": "RESOLVED", "RESOLVED": "VERIFIED"}
    if len(ca):
        aid = st.selectbox("Action", ca.action_id.tolist())
        row = ca.set_index("action_id").loc[aid]
        st.write(f"**{row.action_description}** - status **{row.status}**, assigned to {row.assigned_role}")
        st.dataframe(df(f"/corrective-actions/{aid}/history"), width='stretch')
        if row.status in nxt:
            who = st.text_input("Changed by", "QUALITY_ENGINEER")
            res = st.text_input("Resolution text (required for RESOLVED)") if nxt[row.status] == "RESOLVED" else None
            if st.button(f"Advance to {nxt[row.status]}"):
                if send("PATCH", f"/corrective-actions/{aid}/status", dict(new_status=nxt[row.status], changed_by=who, resolution_text=res or None)):
                    st.success("Status updated - history preserved")
                    st.rerun()
        else:
            st.success("Action is VERIFIED (final).")
    with st.expander("Create a new corrective action"):
        ex = df("/excursions")
        if len(ex):
            eid = st.selectbox("Excursion", ex.excursion_id.tolist())
            desc = st.text_input("Action description")
            prio = st.selectbox("Priority", ["LOW", "MEDIUM", "HIGH"], index=1)
            if st.button("Create") and desc:
                if send("POST", "/corrective-actions", dict(excursion_id=eid, action_description=desc, priority=prio)):
                    st.success("Created")
                    st.rerun()

# ------------------------------------------------------------------------------------------------ Sensors
elif page == "Sensors & data quality":
    st.title("Sensors & data quality")
    se = df("/sensors")
    st.dataframe(se, width='stretch')
    iss = df("/issues")
    a, b = st.columns(2)
    if len(iss):
        cnt = iss.issue_type.value_counts().reset_index()
        cnt.columns = ["issue_type", "count"]
        a.plotly_chart(px.bar(cnt, x="issue_type", y="count", title="Shipment/data-quality issues by type"), width='stretch')
    top = se.sort_values("gap_count", ascending=False).head(10)
    b.plotly_chart(px.bar(top, x="sensor_id", y="gap_count", title="Sensors with most monitoring gaps"), width='stretch')
    st.subheader("Notifications")
    role = st.selectbox("Recipient role", ["ALL", "QUALITY_ENGINEER", "MAINTENANCE_ENGINEER", "PRODUCTION_PLANNER", "OT_IT_ADMIN", "PLANT_OPERATOR"])
    st.dataframe(df("/notifications", recipient_role=role), width='stretch')

# ------------------------------------------------------------------------------------------------ Evaluation
else:
    st.title("Detection evaluation vs ground truth")
    try:
        E = get("/evaluation")
        st.caption(E["level"])
        rows = [dict(issue_type=k, **v) for k, v in E["by_issue_type"].items()]
        st.dataframe(pd.DataFrame(rows), width='stretch')
        st.json({"timing_and_label_errors": E["timing_and_label_errors"], "shipment_level_excursion_detection": E["shipment_level_excursion_detection"]})
    except Exception:
        st.info("Run `python run.py evaluate` to produce the evaluation report.")
