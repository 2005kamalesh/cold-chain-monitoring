"""Unit tests for the detection core using the examples in the problem statement. Run: pytest -q   (or: python tests/test_engine.py)"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from coldchain.engine import find_excursions, find_gaps  # noqa: E402


def frame(minutes_values, lo=2, hi=8, perm=15):
    rows = [dict(shipment_id="S1", sensor_id="SNS-T", measured_at=pd.Timestamp("2026-10-30 10:00") + pd.Timedelta(minutes=m), reading_value=v, lo=lo, hi=hi,
                 policy_id="POL-1", max_excursion_minutes=perm, sensor_type="TEMPERATURE", questionable=False, route_stop_id="RST-1") for m, v in minutes_values]
    return pd.DataFrame(rows)


def test_statement_example_15_minutes():
    # 10:15,10:20,10:25 out of range, 10:30 normal -> start 10:15, end 10:30, 15 min
    e = find_excursions(frame([(0, 5), (5, 6), (10, 7), (15, 9), (20, 11), (25, 12), (30, 7)]))
    assert len(e) == 1 and e.duration_minutes[0] == 15 and e.started_at[0] == pd.Timestamp("2026-10-30 10:15") and e.peak_value[0] == 12
    assert e.is_actionable[0] == 0 and e.severity[0] == "LOW"          # equality with the limit is permissible


def test_duration_not_count_times_five():
    # TC-5: 10:05..10:20 violating (4 readings), recovery 10:25 -> 20 minutes by timestamps
    e = find_excursions(frame([(0, 5), (5, 9), (10, 10), (15, 11), (20, 10), (25, 7)]))
    assert e.duration_minutes[0] == 20 and e.reading_count[0] == 4 and e.is_actionable[0] == 1 and e.severity[0] == "MEDIUM"


def test_missing_readings_inside_excursion_not_undercounted():
    # 2 readings missing inside the excursion: count*5 would say 20, timestamps say 30
    e = find_excursions(frame([(0, 5), (5, 9), (10, 10), (25, 11), (30, 10), (35, 7)]))
    assert e.duration_minutes[0] == 30 and e.has_internal_gap[0] == 1


def test_boundaries_are_inclusive():
    assert find_excursions(frame([(0, 8.0), (5, 8.0), (10, 2.0), (15, 5)])).empty


def test_below_minimum_and_two_excursions():
    e = find_excursions(frame([(0, 5), (5, 1.5), (10, 5), (15, 9), (20, 9), (25, 5)]))
    assert len(e) == 2 and list(e.direction) == ["LOW", "HIGH"] and list(e.duration_minutes) == [5, 10]


def test_end_of_data_closes_at_last_reading_plus_interval():
    e = find_excursions(frame([(0, 5), (5, 9), (10, 10)]))
    assert e.end_reason[0] == "END_OF_DATA" and e.duration_minutes[0] == 10


def test_gap_detection_missing_is_never_safe():
    a = frame([(0, 5), (5, 6), (10, 5), (25, 5), (30, 5)])         # 10:15 and 10:20 missing
    g = find_gaps(a)
    assert len(g) == 1 and g.missing_intervals[0] == 2 and g.gap_minutes[0] == 15 and g.exceeds_tolerance[0] == 0 and g.status[0] == "UNVERIFIED"
    assert find_excursions(a).empty                                  # no excursion invented, gap reported separately


def test_gap_over_tolerance():
    g = find_gaps(frame([(0, 5), (5, 5), (30, 5)]))
    assert g.missing_intervals[0] == 4 and g.exceeds_tolerance[0] == 1


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok ", n)
