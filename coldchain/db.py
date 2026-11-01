"""Thin DB-API layer: works with SQLite (default) and MySQL (pymysql) using the same code path."""
import sqlite3
from pathlib import Path
from urllib.parse import urlparse, unquote

import pandas as pd

from .config import DB_URL

INPUT_TABLES = ["products", "threshold_policies", "containers", "sensors", "sensor_calibrations", "shipments",
                "shipment_sensor_assignments", "shipment_status_events", "route_stops", "custody_events", "sensor_readings"]
DERIVED_TABLES = ["reading_flags", "monitoring_gaps", "excursions", "shipment_issues", "notifications",
                  "corrective_actions", "corrective_action_events", "shipment_summary"]
TABLE_ORDER = INPUT_TABLES + DERIVED_TABLES
DT_SUFFIX = ("_at", "_time", "_from", "_to", "_until", "_start", "_end")


def is_mysql() -> bool:
    return DB_URL.startswith("mysql")


PH = "%s" if is_mysql() else "?"


def connect():
    if is_mysql():
        import pymysql
        u = urlparse(DB_URL.replace("mysql+pymysql://", "mysql://"))
        return pymysql.connect(host=u.hostname, port=u.port or 3306, user=unquote(u.username or ""),
                               password=unquote(u.password or ""), database=u.path.lstrip("/"),
                               charset="utf8mb4", autocommit=False)
    con = sqlite3.connect(DB_URL.replace("sqlite:///", ""))
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_schema():
    """Drop and recreate every table (the generator output is fully reproducible from the seed)."""
    ddl = (Path(__file__).parent / "schema.sql").read_text()
    stmts = [s.strip() for s in "\n".join(l for l in ddl.splitlines() if not l.strip().startswith("--")).split(";") if s.strip()]
    con = connect()
    cur = con.cursor()
    if is_mysql():
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in reversed(TABLE_ORDER):
        cur.execute(f"DROP TABLE IF EXISTS {t}")
    if is_mysql():
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
    for s in stmts:
        cur.execute(s)
    con.commit()
    con.close()


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if c.endswith(DT_SUFFIX):
            df[c] = pd.to_datetime(df[c]).astype("datetime64[ns]")
    return df


def query_df(sql: str, params=()) -> pd.DataFrame:
    con = connect()
    try:
        cur = con.cursor()
        cur.execute(sql.replace("?", PH), tuple(params))
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()
    return parse_dates(pd.DataFrame(rows, columns=cols))


def read_table(name: str) -> pd.DataFrame:
    return query_df(f"SELECT * FROM {name}")


def execute(sql: str, params=()):
    con = connect()
    try:
        cur = con.cursor()
        cur.execute(sql.replace("?", PH), tuple(params))
        con.commit()
    finally:
        con.close()


def write_df(table: str, df: pd.DataFrame, chunk: int = 5000):
    if df.empty:
        return
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    d = d.astype(object).where(d.notna(), None)
    sql = f"INSERT INTO {table} ({','.join(d.columns)}) VALUES ({','.join([PH] * len(d.columns))})"
    con = connect()
    try:
        cur = con.cursor()
        for i in range(0, len(d), chunk):
            cur.executemany(sql, d.iloc[i:i + chunk].values.tolist())
        con.commit()
    finally:
        con.close()
