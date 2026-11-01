# Entity-relationship diagram

Blue = master data, green = input/transaction data, orange = engine-derived tables. Rendered natively on GitHub.

```mermaid
erDiagram
    products ||--o{ threshold_policies : "product_id"
    containers ||--o{ sensors : "container_id"
    sensors ||--o{ sensor_calibrations : "sensor_id"
    products ||--o{ shipments : "product_id"
    containers ||--o{ shipments : "container_id"
    threshold_policies ||--o{ shipments : "policy_id"
    shipments ||--o{ shipment_sensor_assignments : "shipment_id"
    sensors ||--o{ shipment_sensor_assignments : "sensor_id"
    shipments ||--o{ shipment_status_events : "shipment_id"
    shipments ||--o{ route_stops : "shipment_id"
    shipments ||--o{ custody_events : "shipment_id"
    route_stops ||--o{ custody_events : "route_stop_id"
    sensors ||--o{ sensor_readings : "sensor_id"
    shipments ||--o{ sensor_readings : "shipment_id"
    route_stops ||--o{ sensor_readings : "route_stop_id"
    sensor_readings ||--o{ reading_flags : "reading_id"
    shipments ||--o{ monitoring_gaps : "shipment_id"
    sensors ||--o{ monitoring_gaps : "sensor_id"
    shipments ||--o{ excursions : "shipment_id"
    sensors ||--o{ excursions : "sensor_id"
    threshold_policies ||--o{ excursions : "policy_id"
    shipments ||--o{ shipment_issues : "shipment_id"
    shipments ||--o{ notifications : "shipment_id"
    excursions ||--o{ notifications : "excursion_id"
    monitoring_gaps ||--o{ notifications : "gap_id"
    shipment_issues ||--o{ notifications : "issue_id"
    excursions ||--o{ corrective_actions : "excursion_id"
    corrective_actions ||--o{ corrective_action_events : "action_id"
    shipments ||--o{ shipment_summary : "shipment_id"
```

A static image is also provided: `docs/database_schema.png`. Cardinalities are listed in `business_rules.md`.
