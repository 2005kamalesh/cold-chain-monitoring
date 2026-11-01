-- Portable DDL (runs on MySQL 8 and SQLite). Parents first. History tables are append-only by convention.
CREATE TABLE products (
  product_id VARCHAR(12) PRIMARY KEY,
  product_name VARCHAR(80) NOT NULL UNIQUE,
  category VARCHAR(50) NOT NULL,
  storage_class VARCHAR(40) NOT NULL,
  created_at DATETIME NOT NULL
);
CREATE TABLE threshold_policies (
  policy_id VARCHAR(12) PRIMARY KEY,
  product_id VARCHAR(12) NOT NULL,
  version INT NOT NULL,
  min_temperature DOUBLE NOT NULL,
  max_temperature DOUBLE NOT NULL,
  min_humidity DOUBLE NOT NULL,
  max_humidity DOUBLE NOT NULL,
  max_excursion_minutes INT NOT NULL,
  effective_from DATETIME NOT NULL,
  effective_to DATETIME NULL,
  status VARCHAR(12) NOT NULL,
  UNIQUE (product_id, version),
  CHECK (min_temperature < max_temperature),
  CHECK (min_humidity < max_humidity),
  FOREIGN KEY (product_id) REFERENCES products(product_id)
);
CREATE TABLE containers (
  container_id VARCHAR(12) PRIMARY KEY,
  container_type VARCHAR(30) NOT NULL,
  capacity_kg INT NOT NULL,
  status VARCHAR(16) NOT NULL
);
CREATE TABLE sensors (
  sensor_id VARCHAR(32) PRIMARY KEY,
  container_id VARCHAR(12) NOT NULL,
  sensor_type VARCHAR(12) NOT NULL,
  unit VARCHAR(6) NOT NULL,
  model VARCHAR(40) NOT NULL,
  status VARCHAR(12) NOT NULL,
  installed_at DATETIME NOT NULL,
  FOREIGN KEY (container_id) REFERENCES containers(container_id)
);
CREATE TABLE sensor_calibrations (
  calibration_id VARCHAR(12) PRIMARY KEY,
  sensor_id VARCHAR(32) NOT NULL,
  calibrated_at DATETIME NOT NULL,
  valid_until DATETIME NOT NULL,
  result VARCHAR(8) NOT NULL,
  CHECK (calibrated_at < valid_until),
  FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);
CREATE TABLE shipments (
  shipment_id VARCHAR(16) PRIMARY KEY,
  product_id VARCHAR(12) NOT NULL,
  container_id VARCHAR(12) NOT NULL,
  policy_id VARCHAR(12) NOT NULL,
  origin VARCHAR(40) NOT NULL,
  destination VARCHAR(40) NOT NULL,
  carrier VARCHAR(40) NOT NULL,
  planned_departure_at DATETIME NOT NULL,
  planned_arrival_at DATETIME NOT NULL,
  actual_departure_at DATETIME NULL,
  actual_delivery_at DATETIME NULL,
  status VARCHAR(12) NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(product_id),
  FOREIGN KEY (container_id) REFERENCES containers(container_id),
  FOREIGN KEY (policy_id) REFERENCES threshold_policies(policy_id)
);
CREATE TABLE shipment_sensor_assignments (
  assignment_id VARCHAR(16) PRIMARY KEY,
  shipment_id VARCHAR(16) NOT NULL,
  sensor_id VARCHAR(32) NOT NULL,
  assigned_at DATETIME NOT NULL,
  released_at DATETIME NULL,
  UNIQUE (shipment_id, sensor_id),
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
  FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);
CREATE TABLE shipment_status_events (
  status_event_id VARCHAR(12) PRIMARY KEY,
  shipment_id VARCHAR(16) NOT NULL,
  previous_status VARCHAR(12) NULL,
  new_status VARCHAR(12) NOT NULL,
  changed_by VARCHAR(40) NOT NULL,
  changed_at DATETIME NOT NULL,
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id)
);
CREATE TABLE route_stops (
  route_stop_id VARCHAR(32) PRIMARY KEY,
  shipment_id VARCHAR(16) NOT NULL,
  stop_sequence INT NOT NULL,
  location VARCHAR(40) NOT NULL,
  stop_type VARCHAR(14) NOT NULL,
  planned_arrival_at DATETIME NOT NULL,
  planned_departure_at DATETIME NULL,
  actual_arrival_at DATETIME NULL,
  actual_departure_at DATETIME NULL,
  UNIQUE (shipment_id, stop_sequence),
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id)
);
CREATE TABLE custody_events (
  custody_event_id VARCHAR(12) PRIMARY KEY,
  shipment_id VARCHAR(16) NOT NULL,
  route_stop_id VARCHAR(32) NOT NULL,
  event_seq INT NOT NULL,
  event_type VARCHAR(24) NOT NULL,
  from_party VARCHAR(60) NOT NULL,
  to_party VARCHAR(60) NOT NULL,
  location VARCHAR(40) NOT NULL,
  event_time DATETIME NOT NULL,
  UNIQUE (shipment_id, event_seq),
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
  FOREIGN KEY (route_stop_id) REFERENCES route_stops(route_stop_id)
);
CREATE TABLE sensor_readings (
  reading_id VARCHAR(64) PRIMARY KEY,
  sensor_id VARCHAR(32) NOT NULL,
  shipment_id VARCHAR(16) NOT NULL,
  route_stop_id VARCHAR(32) NOT NULL,
  measured_at DATETIME NOT NULL,
  received_at DATETIME NOT NULL,
  reading_value DOUBLE NOT NULL,
  unit VARCHAR(6) NOT NULL,
  UNIQUE (sensor_id, measured_at),
  FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id),
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
  FOREIGN KEY (route_stop_id) REFERENCES route_stops(route_stop_id)
);
CREATE INDEX idx_readings_shipment ON sensor_readings (shipment_id, sensor_id, measured_at);
CREATE TABLE reading_flags (
  reading_id VARCHAR(64) NOT NULL,
  flag_type VARCHAR(30) NOT NULL,
  detail VARCHAR(120) NULL,
  PRIMARY KEY (reading_id, flag_type),
  FOREIGN KEY (reading_id) REFERENCES sensor_readings(reading_id)
);
CREATE TABLE monitoring_gaps (
  gap_id VARCHAR(12) PRIMARY KEY,
  shipment_id VARCHAR(16) NOT NULL,
  sensor_id VARCHAR(32) NOT NULL,
  route_stop_id VARCHAR(32) NULL,
  gap_start DATETIME NOT NULL,
  gap_end DATETIME NOT NULL,
  gap_minutes INT NOT NULL,
  missing_intervals INT NOT NULL,
  exceeds_tolerance TINYINT NOT NULL,
  status VARCHAR(12) NOT NULL,
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
  FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
);
CREATE TABLE excursions (
  excursion_id VARCHAR(16) PRIMARY KEY,
  shipment_id VARCHAR(16) NOT NULL,
  sensor_id VARCHAR(32) NOT NULL,
  policy_id VARCHAR(12) NOT NULL,
  route_stop_id VARCHAR(32) NULL,
  excursion_type VARCHAR(12) NOT NULL,
  direction VARCHAR(4) NOT NULL,
  started_at DATETIME NOT NULL,
  ended_at DATETIME NOT NULL,
  end_reason VARCHAR(20) NOT NULL,
  duration_minutes INT NOT NULL,
  peak_value DOUBLE NOT NULL,
  limit_value DOUBLE NOT NULL,
  max_permissible_minutes INT NOT NULL,
  reading_count INT NOT NULL,
  has_internal_gap TINYINT NOT NULL,
  data_quality VARCHAR(12) NOT NULL,
  is_actionable TINYINT NOT NULL,
  severity VARCHAR(8) NOT NULL,
  status VARCHAR(20) NOT NULL,
  responsible_party VARCHAR(60) NULL,
  detected_at DATETIME NOT NULL,
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
  FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id),
  FOREIGN KEY (policy_id) REFERENCES threshold_policies(policy_id)
);
CREATE TABLE shipment_issues (
  issue_id VARCHAR(12) PRIMARY KEY,
  shipment_id VARCHAR(16) NOT NULL,
  sensor_id VARCHAR(32) NULL,
  issue_type VARCHAR(30) NOT NULL,
  severity VARCHAR(8) NOT NULL,
  detail VARCHAR(255) NULL,
  detected_at DATETIME NOT NULL,
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id)
);
CREATE TABLE notifications (
  notification_id VARCHAR(12) PRIMARY KEY,
  shipment_id VARCHAR(16) NOT NULL,
  excursion_id VARCHAR(16) NULL,
  gap_id VARCHAR(12) NULL,
  issue_id VARCHAR(12) NULL,
  notification_type VARCHAR(30) NOT NULL,
  severity VARCHAR(8) NOT NULL,
  recipient_role VARCHAR(24) NOT NULL,
  message VARCHAR(400) NOT NULL,
  created_at DATETIME NOT NULL,
  status VARCHAR(14) NOT NULL,
  acknowledged_at DATETIME NULL,
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
  FOREIGN KEY (excursion_id) REFERENCES excursions(excursion_id),
  FOREIGN KEY (gap_id) REFERENCES monitoring_gaps(gap_id),
  FOREIGN KEY (issue_id) REFERENCES shipment_issues(issue_id)
);
CREATE TABLE corrective_actions (
  action_id VARCHAR(12) PRIMARY KEY,
  excursion_id VARCHAR(16) NOT NULL,
  assigned_role VARCHAR(24) NOT NULL,
  action_description VARCHAR(200) NOT NULL,
  priority VARCHAR(8) NOT NULL,
  status VARCHAR(12) NOT NULL,
  created_at DATETIME NOT NULL,
  due_at DATETIME NOT NULL,
  resolution_text VARCHAR(200) NULL,
  last_updated_at DATETIME NOT NULL,
  FOREIGN KEY (excursion_id) REFERENCES excursions(excursion_id)
);
CREATE TABLE corrective_action_events (
  event_id VARCHAR(12) PRIMARY KEY,
  action_id VARCHAR(12) NOT NULL,
  previous_status VARCHAR(12) NULL,
  new_status VARCHAR(12) NOT NULL,
  changed_by VARCHAR(24) NOT NULL,
  changed_at DATETIME NOT NULL,
  reason VARCHAR(200) NULL,
  FOREIGN KEY (action_id) REFERENCES corrective_actions(action_id)
);
CREATE TABLE shipment_summary (
  shipment_id VARCHAR(16) PRIMARY KEY,
  product_id VARCHAR(12) NOT NULL,
  status VARCHAR(12) NOT NULL,
  compliance_status VARCHAR(24) NOT NULL,
  excursion_count INT NOT NULL,
  actionable_excursions INT NOT NULL,
  gap_count INT NOT NULL,
  gaps_over_tolerance INT NOT NULL,
  unverified_minutes INT NOT NULL,
  questionable_readings INT NOT NULL,
  invalid_readings INT NOT NULL,
  issue_count INT NOT NULL,
  delay_minutes INT NULL,
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id)
);
