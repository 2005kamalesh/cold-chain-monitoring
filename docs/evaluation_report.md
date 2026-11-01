# Detection evaluation vs ground truth

instance (1 injected anomaly = 1 unit); shipment-level confusion matrix reported separately for excursions

| Issue type | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| TEMPERATURE_EXCURSION | 192 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| HUMIDITY_EXCURSION | 65 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| MISSING_INTERVAL | 137 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| PHYSICAL_RANGE_VIOLATION | 26 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| DELIVERY_BEFORE_DEPARTURE | 8 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| POLICY_MISMATCH | 8 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| ROUTE_DELAY | 55 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| CALIBRATION_EXPIRED | 50 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| LATE_ARRIVAL | 37 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| BOUNDARY_INCLUSIVE (no excursion expected) | cases=10, false excursions=0 | | | | | |

## Timing / label accuracy (matched excursions)
```
{
  "TEMPERATURE": {
    "matched": 192,
    "duration_abs_error_min_max": 0.0,
    "end_time_exact": 1.0,
    "severity_accuracy": 1.0,
    "actionable_accuracy": 1.0
  },
  "HUMIDITY": {
    "matched": 65,
    "duration_abs_error_min_max": 0.0,
    "end_time_exact": 1.0,
    "severity_accuracy": 1.0,
    "actionable_accuracy": 1.0
  },
  "MISSING_INTERVAL": {
    "missing_interval_count_exact": 1.0,
    "tolerance_flag_accuracy": 1.0
  }
}
```

## Shipment-level excursion detection
```
{
  "TP": 253,
  "FP": 0,
  "FN": 0,
  "precision": 1.0,
  "recall": 1.0,
  "f1": 1.0,
  "TN": 747
}
```
