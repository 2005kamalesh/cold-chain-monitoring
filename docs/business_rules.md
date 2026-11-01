# Business rules & design decisions

| Decision | Rule |
|---|---|
| Limits | Inclusive: value == min or max is IN range |
| Excursion start | First valid out-of-range reading |
| Excursion end | First subsequent valid in-range reading (recovery). If none: last violating reading + 5 min, `end_reason=END_OF_DATA` |
| Duration | `ended_at - started_at` from timestamps (never count x 5). Missing readings inside an excursion do not shorten it (`has_internal_gap=1`) |
| Permissible duration | CONSECUTIVE (not cumulative); actionable only if duration is STRICTLY greater than `max_excursion_minutes` |
| Severity | LOW = permissible, MEDIUM = actionable and <= 2x permissible, HIGH = > 2x |
| Missing readings | `monitoring_gaps` row, status UNVERIFIED, never safe. Alert if gap (next - previous timestamp) > 15 min |
| Invalid readings | Outside plausible physical range (-50..60 C, 0..100 %RH): preserved, flagged, excluded from excursion logic |
| Calibration | Reading is QUESTIONABLE if no PASS calibration covers `calibrated_at <= t < valid_until`; still evaluated, excursion marked `data_quality=QUESTIONABLE` |
| Late arrival | `received_at - measured_at` > 30 min: flagged; measurement time is what counts |
| Policy | Effective-dated: policy valid at the READING time (v2 effective 2026-09-15 shortens permissible duration by 5 min) |
| Wrong policy | Shipment.policy_id whose product differs from the shipment's product => POLICY_MISMATCH; engine still uses the correct policy |
| Route delay | Delivered > 60 min after planned arrival |
| Containers | 1 shipment : 1 container; a container is reused only after release + 12 h; no overlaps (validated) |
| History | Corrective-action status changes are append-only events; derived tables are rebuilt each engine run |

Corrective-action lifecycle: OPEN -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> VERIFIED (no skipping; RESOLVED needs resolution text).
Excursion status: not actionable => CLOSED; actionable => OPEN / UNDER_INVESTIGATION / CLOSED (all actions VERIFIED).

## Test-case coverage
| Case | Where |
|---|---|
| Reading outside physical range | generator `EDGE_PHYSICAL_RANGE`; engine flag; evaluated |
| Missing interval read as safe | dropouts => gaps UNVERIFIED; unit test `test_gap_detection_missing_is_never_safe` |
| Delivered before departure | injected, flagged `DELIVERY_BEFORE_DEPARTURE`, dates not corrected |
| Threshold applied to wrong product | injected, `POLICY_MISMATCH` with expected policy in detail |
| Duration undercounted | `EXC_WITH_INTERNAL_GAP` scenario + unit tests |
| Boundary equal to limit (TC-06/07) | `BOUNDARY_INCLUSIVE`, must NOT create an excursion |
| Brief / prolonged / multiple excursions (TC-08/09/23) | BRIEF, PROLONGED, MULTI scenarios |
| Humidity high/low (TC-10/11) | humidity excursions, both directions |
| Calibration expired (TC-12) | CALIBRATION scenario |
| Late arrival (TC-22) | DROPOUT scenario (25% of blocks) |
| Policy changes mid-shipment (TC-21) | policy v2 on 2026-09-15 |
| Container overlap (TC-17), route order (TC-18), custody order (TC-19), duplicates (TC-14), orphans (TC-15/16), action workflow (TC-20), no sensor (TC-25) | checked by validation / engine; NOT injected as faults in this MVP |
| Concurrent temperature + humidity overlap (TC-24) | not injected |

## Cardinality, optional relationships, lifecycles
| Relationship | Cardinality | Notes |
|---|---|---|
| Product -> ThresholdPolicy | 1:N | effective-dated versions; non-overlapping per product |
| Product -> Shipment | 1:N | |
| ThresholdPolicy -> Shipment | 1:N | policy assigned at creation; mismatch with product is flagged |
| Container -> Sensor | 1:N | one TEMP + one HUM sensor per container |
| Sensor -> SensorCalibration | 1:N | effective-dated; a gap between records = calibration lapse |
| Container -> Shipment | 1:N over time, 1:1 at any moment | no overlapping use (validated) |
| Shipment <-> Sensor | N:M | bridge table `shipment_sensor_assignments` (assigned_at / released_at) |
| Shipment -> RouteStop | 1:N | ordered by `stop_sequence`; origin, 1-2 transit hubs, destination |
| Shipment -> CustodyEvent | 1:N | ordered by `event_seq`; references a route stop |
| Shipment -> ShipmentStatusEvent | 1:N | append-only lifecycle history |
| Sensor -> SensorReading | 1:N | each reading also references its shipment and the last route stop reached |
| Shipment -> Excursion | 1:N | optional (a compliant shipment has none) |
| Excursion -> CorrectiveAction | 1:N, optional | only actionable excursions get actions automatically; HIGH gets two |
| CorrectiveAction -> CorrectiveActionEvent | 1:N | append-only status history |
| Excursion / Gap / Issue -> Notification | 1:N, each FK optional | one notification row references exactly one source |

Shipment lifecycle: CREATED -> DISPATCHED -> IN_TRANSIT -> DELIVERED (all shipments end DELIVERED in this dataset).
