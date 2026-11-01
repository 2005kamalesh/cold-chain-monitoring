# Validation report

85/85 checks passed

| Check | Result | Detail |
|---|---|---|
| PK unique: products | PASS | 0 duplicates |
| PK unique: threshold_policies | PASS | 0 duplicates |
| PK unique: containers | PASS | 0 duplicates |
| PK unique: sensors | PASS | 0 duplicates |
| PK unique: sensor_calibrations | PASS | 0 duplicates |
| PK unique: shipments | PASS | 0 duplicates |
| PK unique: shipment_sensor_assignments | PASS | 0 duplicates |
| PK unique: shipment_status_events | PASS | 0 duplicates |
| PK unique: route_stops | PASS | 0 duplicates |
| PK unique: custody_events | PASS | 0 duplicates |
| PK unique: sensor_readings | PASS | 0 duplicates |
| PK unique: monitoring_gaps | PASS | 0 duplicates |
| PK unique: excursions | PASS | 0 duplicates |
| PK unique: shipment_issues | PASS | 0 duplicates |
| PK unique: notifications | PASS | 0 duplicates |
| PK unique: corrective_actions | PASS | 0 duplicates |
| PK unique: corrective_action_events | PASS | 0 duplicates |
| PK unique: reading_flags | PASS | 0 duplicates |
| PK unique: shipment_summary | PASS | 0 duplicates |
| FK valid: threshold_policies.product_id -> products | PASS | 0 orphans |
| FK valid: sensors.container_id -> containers | PASS | 0 orphans |
| FK valid: sensor_calibrations.sensor_id -> sensors | PASS | 0 orphans |
| FK valid: shipments.product_id -> products | PASS | 0 orphans |
| FK valid: shipments.container_id -> containers | PASS | 0 orphans |
| FK valid: shipments.policy_id -> threshold_policies | PASS | 0 orphans |
| FK valid: shipment_sensor_assignments.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: shipment_sensor_assignments.sensor_id -> sensors | PASS | 0 orphans |
| FK valid: shipment_status_events.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: route_stops.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: custody_events.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: custody_events.route_stop_id -> route_stops | PASS | 0 orphans |
| FK valid: sensor_readings.sensor_id -> sensors | PASS | 0 orphans |
| FK valid: sensor_readings.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: sensor_readings.route_stop_id -> route_stops | PASS | 0 orphans |
| FK valid: reading_flags.reading_id -> sensor_readings | PASS | 0 orphans |
| FK valid: monitoring_gaps.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: monitoring_gaps.sensor_id -> sensors | PASS | 0 orphans |
| FK valid: excursions.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: excursions.sensor_id -> sensors | PASS | 0 orphans |
| FK valid: excursions.policy_id -> threshold_policies | PASS | 0 orphans |
| FK valid: shipment_issues.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: notifications.shipment_id -> shipments | PASS | 0 orphans |
| FK valid: notifications.excursion_id -> excursions | PASS | 0 orphans |
| FK valid: notifications.gap_id -> monitoring_gaps | PASS | 0 orphans |
| FK valid: notifications.issue_id -> shipment_issues | PASS | 0 orphans |
| FK valid: corrective_actions.excursion_id -> excursions | PASS | 0 orphans |
| FK valid: corrective_action_events.action_id -> corrective_actions | PASS | 0 orphans |
| FK valid: shipment_summary.shipment_id -> shipments | PASS | 0 orphans |
| Enum: shipments.status | PASS | 0 invalid |
| Enum: sensors.sensor_type | PASS | 0 invalid |
| Enum: shipment_status_events.new_status | PASS | 0 invalid |
| Enum: sensors.unit | PASS | 0 invalid |
| Enum: sensor_calibrations.result | PASS | 0 invalid |
| Enum: route_stops.stop_type | PASS | 0 invalid |
| Enum: custody_events.event_type | PASS | 0 invalid |
| Enum: excursions.excursion_type | PASS | 0 invalid |
| Enum: excursions.direction | PASS | 0 invalid |
| Enum: excursions.severity | PASS | 0 invalid |
| Enum: excursions.status | PASS | 0 invalid |
| Enum: corrective_actions.status | PASS | 0 invalid |
| Enum: monitoring_gaps.status | PASS | 0 invalid |
| Enum: notifications.status | PASS | 0 invalid |
| Date order: delivery >= departure (excluding labelled DELIVERY_BEFORE_DEPARTURE cases) | PASS | 8 violations, 0 unlabelled |
| Date order: planned arrival > planned departure | PASS |  |
| Route stop times ascend with sequence | PASS |  |
| Policy effective_from < effective_to | PASS |  |
| Policies of one product do not overlap | PASS |  |
| Lifecycle: shipment CREATED->DISPATCHED->IN_TRANSIT->DELIVERED in time order (labelled cases excused) | PASS | 8 violations, 0 unlabelled |
| Assigned sensors are installed in the shipment's container | PASS |  |
| Every shipment has a sensor assigned (monitoring coverage) | PASS | 0 uncovered |
| Custody timeline ordered | PASS |  |
| No custody event before dispatch | PASS |  |
| Duplicate readings (sensor, timestamp) | PASS |  |
| Readings link to the right shipment (sensor container == shipment container) | PASS |  |
| Readings link to a route stop of the same shipment | PASS |  |
| No container assigned to overlapping shipments | PASS | 0 overlaps |
| Reconcile: excursion duration == (ended - started) minutes | PASS |  |
| Reconcile: actionable <=> duration > permissible | PASS |  |
| Reconcile: gap missing_intervals == gap_minutes/5 - 1 | PASS |  |
| Reconcile: expected intervals == received + missing (per shipment, both sensors averaged) | PASS | max diff 0.0 |
| Reconcile: summary excursion_count == excursions rows | PASS |  |
| Lifecycle: corrective action OPEN->ASSIGNED->IN_PROGRESS->RESOLVED->VERIFIED, no skipped/VERIFIED-without-RESOLVED | PASS |  |
| Lifecycle: action.status == last history event | PASS |  |
| Every actionable excursion has >=1 corrective action and a notification | PASS |  |
| Excursion duplicates (shipment, sensor, start) | PASS |  |
