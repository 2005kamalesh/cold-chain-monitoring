# Data dictionary

Generated from `coldchain/schema.sql`. PK = primary key, FK = foreign key.

## products

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| product_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| product_name | VARCHAR(80) | Yes | UNIQUE |  |  |
| category | VARCHAR(50) | Yes |  |  |  |
| storage_class | VARCHAR(40) | Yes |  |  |  |
| created_at | DATETIME | Yes |  |  |  |

## threshold_policies

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| policy_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| product_id | VARCHAR(12) | Yes | FK -> products |  |  |
| version | INT | Yes |  |  |  |
| min_temperature | DOUBLE | Yes |  | C | C; < max_temperature |
| max_temperature | DOUBLE | Yes |  | C | C; > min_temperature |
| min_humidity | DOUBLE | Yes |  | %RH | %RH; < max_humidity |
| max_humidity | DOUBLE | Yes |  | %RH | %RH; > min_humidity |
| max_excursion_minutes | INT | Yes |  | min | minutes; CONSECUTIVE permissible duration; action only if duration > value |
| effective_from | DATETIME | Yes |  |  | inclusive start of policy validity |
| effective_to | DATETIME | Optional |  |  | exclusive end; NULL = open-ended |
| status | VARCHAR(12) | Yes |  |  | enum (see business_rules.md lifecycle section) |

Composite unique: (product_id, version)

## containers

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| container_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| container_type | VARCHAR(30) | Yes |  |  |  |
| capacity_kg | INT | Yes |  | kg |  |
| status | VARCHAR(16) | Yes |  |  | enum (see business_rules.md lifecycle section) |

## sensors

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| sensor_id | VARCHAR(32) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| container_id | VARCHAR(12) | Yes | FK -> containers |  |  |
| sensor_type | VARCHAR(12) | Yes |  |  |  |
| unit | VARCHAR(6) | Yes |  |  |  |
| model | VARCHAR(40) | Yes |  |  |  |
| status | VARCHAR(12) | Yes |  |  | enum (see business_rules.md lifecycle section) |
| installed_at | DATETIME | Yes |  |  |  |

## sensor_calibrations

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| calibration_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| sensor_id | VARCHAR(32) | Yes | FK -> sensors |  |  |
| calibrated_at | DATETIME | Yes |  |  |  |
| valid_until | DATETIME | Yes |  |  | calibration valid while calibrated_at <= t < valid_until |
| result | VARCHAR(8) | Yes |  |  |  |

## shipments

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| shipment_id | VARCHAR(16) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| product_id | VARCHAR(12) | Yes | FK -> products |  |  |
| container_id | VARCHAR(12) | Yes | FK -> containers |  |  |
| policy_id | VARCHAR(12) | Yes | FK -> threshold_policies |  | FK; policy's product must equal the shipment's product (else POLICY_MISMATCH) |
| origin | VARCHAR(40) | Yes |  |  |  |
| destination | VARCHAR(40) | Yes |  |  |  |
| carrier | VARCHAR(40) | Yes |  |  |  |
| planned_departure_at | DATETIME | Yes |  |  |  |
| planned_arrival_at | DATETIME | Yes |  |  |  |
| actual_departure_at | DATETIME | Optional |  |  |  |
| actual_delivery_at | DATETIME | Optional |  |  | must be >= actual_departure_at (violations are flagged DELIVERY_BEFORE_DEPARTURE, never silently fixed) |
| status | VARCHAR(12) | Yes |  |  | enum (see business_rules.md lifecycle section) |

## shipment_sensor_assignments

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| assignment_id | VARCHAR(16) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| sensor_id | VARCHAR(32) | Yes | FK -> sensors |  |  |
| assigned_at | DATETIME | Yes |  |  |  |
| released_at | DATETIME | Optional |  |  |  |

Composite unique: (shipment_id, sensor_id)

## shipment_status_events

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| status_event_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| previous_status | VARCHAR(12) | Optional |  |  |  |
| new_status | VARCHAR(12) | Yes |  |  |  |
| changed_by | VARCHAR(40) | Yes |  |  |  |
| changed_at | DATETIME | Yes |  |  |  |

## route_stops

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| route_stop_id | VARCHAR(32) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| stop_sequence | INT | Yes |  |  |  |
| location | VARCHAR(40) | Yes |  |  |  |
| stop_type | VARCHAR(14) | Yes |  |  |  |
| planned_arrival_at | DATETIME | Yes |  |  |  |
| planned_departure_at | DATETIME | Optional |  |  |  |
| actual_arrival_at | DATETIME | Optional |  |  |  |
| actual_departure_at | DATETIME | Optional |  |  |  |

Composite unique: (shipment_id, stop_sequence)

## custody_events

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| custody_event_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| route_stop_id | VARCHAR(32) | Yes | FK -> route_stops |  |  |
| event_seq | INT | Yes |  |  |  |
| event_type | VARCHAR(24) | Yes |  |  |  |
| from_party | VARCHAR(60) | Yes |  |  |  |
| to_party | VARCHAR(60) | Yes |  |  |  |
| location | VARCHAR(40) | Yes |  |  |  |
| event_time | DATETIME | Yes |  |  | custody events strictly ordered by event_seq |

Composite unique: (shipment_id, event_seq)

## sensor_readings

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| reading_id | VARCHAR(64) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| sensor_id | VARCHAR(32) | Yes | FK -> sensors |  |  |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| route_stop_id | VARCHAR(32) | Yes | FK -> route_stops |  |  |
| measured_at | DATETIME | Yes |  |  | datetime; 5-minute grid within the journey; unique per sensor |
| received_at | DATETIME | Yes |  |  | datetime >= measured_at; late if > 30 min |
| reading_value | DOUBLE | Yes |  | C or %RH | float; physical range -50..60 C / 0..100 %RH (plausibility) - outside => INVALID, preserved, excluded |
| unit | VARCHAR(6) | Yes |  |  |  |

Composite unique: (sensor_id, measured_at)

## reading_flags

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| reading_id | VARCHAR(64) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| flag_type | VARCHAR(30) | Yes | PK |  |  |
| detail | VARCHAR(120) | Optional |  |  |  |

## monitoring_gaps

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| gap_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| sensor_id | VARCHAR(32) | Yes | FK -> sensors |  |  |
| route_stop_id | VARCHAR(32) | Optional |  |  |  |
| gap_start | DATETIME | Yes |  |  |  |
| gap_end | DATETIME | Yes |  |  |  |
| gap_minutes | INT | Yes |  | min |  |
| missing_intervals | INT | Yes |  |  | gap_minutes/5 - 1 |
| exceeds_tolerance | TINYINT | Yes |  |  | 1 iff gap_minutes > 15 |
| status | VARCHAR(12) | Yes |  |  | enum (see business_rules.md lifecycle section) |

## excursions

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| excursion_id | VARCHAR(16) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| sensor_id | VARCHAR(32) | Yes | FK -> sensors |  |  |
| policy_id | VARCHAR(12) | Yes | FK -> threshold_policies |  | FK; policy's product must equal the shipment's product (else POLICY_MISMATCH) |
| route_stop_id | VARCHAR(32) | Optional |  |  |  |
| excursion_type | VARCHAR(12) | Yes |  |  |  |
| direction | VARCHAR(4) | Yes |  |  |  |
| started_at | DATETIME | Yes |  |  |  |
| ended_at | DATETIME | Yes |  |  |  |
| end_reason | VARCHAR(20) | Yes |  |  | RECOVERED / DIRECTION_CHANGE / END_OF_DATA |
| duration_minutes | INT | Yes |  | min | (ended_at - started_at) in minutes; never count*5 |
| peak_value | DOUBLE | Yes |  | C or %RH |  |
| limit_value | DOUBLE | Yes |  | C or %RH |  |
| max_permissible_minutes | INT | Yes |  | min |  |
| reading_count | INT | Yes |  |  |  |
| has_internal_gap | TINYINT | Yes |  |  |  |
| data_quality | VARCHAR(12) | Yes |  |  | QUESTIONABLE if any reading in the excursion lacked valid calibration |
| is_actionable | TINYINT | Yes |  |  | 1 iff duration_minutes > max_permissible_minutes |
| severity | VARCHAR(8) | Yes |  |  | LOW (<= permissible) / MEDIUM (<= 2x) / HIGH (> 2x) |
| status | VARCHAR(20) | Yes |  |  | enum (see business_rules.md lifecycle section) |
| responsible_party | VARCHAR(60) | Optional |  |  |  |
| detected_at | DATETIME | Yes |  |  |  |

## shipment_issues

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| issue_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| sensor_id | VARCHAR(32) | Optional |  |  |  |
| issue_type | VARCHAR(30) | Yes |  |  |  |
| severity | VARCHAR(8) | Yes |  |  | LOW (<= permissible) / MEDIUM (<= 2x) / HIGH (> 2x) |
| detail | VARCHAR(255) | Optional |  |  |  |
| detected_at | DATETIME | Yes |  |  |  |

## notifications

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| notification_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| shipment_id | VARCHAR(16) | Yes | FK -> shipments |  |  |
| excursion_id | VARCHAR(16) | Optional | FK -> excursions |  |  |
| gap_id | VARCHAR(12) | Optional | FK -> monitoring_gaps |  |  |
| issue_id | VARCHAR(12) | Optional | FK -> shipment_issues |  |  |
| notification_type | VARCHAR(30) | Yes |  |  |  |
| severity | VARCHAR(8) | Yes |  |  | LOW (<= permissible) / MEDIUM (<= 2x) / HIGH (> 2x) |
| recipient_role | VARCHAR(24) | Yes |  |  |  |
| message | VARCHAR(400) | Yes |  |  |  |
| created_at | DATETIME | Yes |  |  |  |
| status | VARCHAR(14) | Yes |  |  | enum (see business_rules.md lifecycle section) |
| acknowledged_at | DATETIME | Optional |  |  |  |

## corrective_actions

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| action_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| excursion_id | VARCHAR(16) | Yes | FK -> excursions |  |  |
| assigned_role | VARCHAR(24) | Yes |  |  |  |
| action_description | VARCHAR(200) | Yes |  |  |  |
| priority | VARCHAR(8) | Yes |  |  |  |
| status | VARCHAR(12) | Yes |  |  | enum (see business_rules.md lifecycle section) |
| created_at | DATETIME | Yes |  |  |  |
| due_at | DATETIME | Yes |  |  |  |
| resolution_text | VARCHAR(200) | Optional |  |  |  |
| last_updated_at | DATETIME | Yes |  |  |  |

## corrective_action_events

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| event_id | VARCHAR(12) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| action_id | VARCHAR(12) | Yes | FK -> corrective_actions |  |  |
| previous_status | VARCHAR(12) | Optional |  |  |  |
| new_status | VARCHAR(12) | Yes |  |  |  |
| changed_by | VARCHAR(24) | Yes |  |  |  |
| changed_at | DATETIME | Yes |  |  |  |
| reason | VARCHAR(200) | Optional |  |  |  |

## shipment_summary

| Field | Type | Required | Key | Unit | Validation / rule |
|---|---|---|---|---|---|
| shipment_id | VARCHAR(16) | Yes | PK |  | immutable deterministic ID (see README nomenclature) |
| product_id | VARCHAR(12) | Yes |  |  |  |
| status | VARCHAR(12) | Yes |  |  | enum (see business_rules.md lifecycle section) |
| compliance_status | VARCHAR(24) | Yes |  |  |  |
| excursion_count | INT | Yes |  |  |  |
| actionable_excursions | INT | Yes |  |  |  |
| gap_count | INT | Yes |  |  |  |
| gaps_over_tolerance | INT | Yes |  |  |  |
| unverified_minutes | INT | Yes |  | min |  |
| questionable_readings | INT | Yes |  |  |  |
| invalid_readings | INT | Yes |  |  |  |
| issue_count | INT | Yes |  |  |  |
| delay_minutes | INT | Optional |  | min |  |
