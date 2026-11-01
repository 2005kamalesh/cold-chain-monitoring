# Test-case and edge-case matrix

Validation: **85/85** checks pass. Unit tests: `tests/test_engine.py` (8), `tests/test_negative_cases.py` (8). Detection results below are from the full dataset (`evaluation_report.md`).

## Mandatory negative scenarios (from the assignment)

| # | Scenario | How it is injected | Expected behaviour | Result |
|---|---|---|---|---|
| 1 | Reading outside physical range | Replaces some readings with 150 / 250 / -100 (temp) or 130 / 250 / -20 (RH) in labelled shipments | Flag INVALID, preserve original, exclude from excursion logic, create data-quality issue | TP 26 / FP 0 / FN 0 |
| 2 | Missing interval interpreted as safe | Dropout blocks removed from the stream | Gap record, status UNVERIFIED, never counted as compliant; alert if > 15 min | TP 137 / FP 0 / FN 0 |
| 3 | Shipment delivered before departure | `actual_delivery_at` set 5-48 h before departure | DELIVERY_BEFORE_DEPARTURE issue, dates not corrected | TP 8 / FP 0 / FN 0 |
| 4 | Threshold applied to wrong product | Shipment gets another product's policy id | POLICY_MISMATCH, correct effective policy used for judging readings | TP 8 / FP 0 / FN 0 |
| 5 | Excursion duration undercounted | Excursion with 2-3 missing readings inside it (count x 5 would be shorter) | Duration from timestamps (recovery - start) | duration error max 0.0 min over all temperature matches |

## Coverage of other required behaviour

| Behaviour | Evidence |
|---|---|
| Brief / prolonged / multiple excursions | Scenarios BRIEF, PROLONGED, MULTI; temperature TP 192 / FP 0 / FN 0, humidity TP 65 / FP 0 / FN 0 |
| Boundary values equal to limit are in range | BOUNDARY_INCLUSIVE shipments produce no excursion; `test_boundaries_are_inclusive` |
| Humidity high and low | Both directions generated; evaluation matches |
| Calibration failure (reading reliability) | Calibration lapse mid-trip; TP 50 / FP 0 / FN 0 |
| Late-arriving readings | received_at after measured_at by 35-90 min; TP 37 / FP 0 / FN 0 |
| Route delays | Delay at a route stop; TP 55 / FP 0 / FN 0 |
| Policy effective-dated (policy changes during shipment) | Policy v2 effective 2026-09-15; engine picks the policy valid at each reading time |
| Duplicate reading id / duplicate sensor+timestamp | DB UNIQUE constraints, validation check, `test_duplicate_reading_and_duplicate_id` |
| Orphan sensor / orphan shipment | FK constraints + validation, `test_orphan_sensor_and_orphan_shipment` |
| Container assigned to overlapping shipments | Generator prevents; validation + `test_container_assigned_to_overlapping_shipments` |
| Route stops in wrong order / custody before dispatch / custody unordered | Validation + engine issue types; negative tests |
| Shipment lifecycle order | `shipment_status_events` validated; negative test for skipped status |
| Corrective action closed without verification | API rejects skipped transitions (409); validation checks event chain |
| Shipment without sensor | Validation of `shipment_sensor_assignments`; engine NO_MONITORING_DATA; negative test |
| Temperature + humidity violations overlapping in time | Handled independently per sensor stream; not deliberately injected as a joint case |

## Acceptance criteria

| Criterion | Evidence |
|---|---|
| Excursions follow threshold/duration rules | Reconciliation checks in `validation_report.md`; evaluation severity/actionable accuracy 100% |
| Gaps are flagged | MISSING_INTERVAL evaluation + UNVERIFIED status |
| Readings link to correct shipment and route | Relationship checks in validation report |
| Custody timeline is ordered | Custody check in validation report |
