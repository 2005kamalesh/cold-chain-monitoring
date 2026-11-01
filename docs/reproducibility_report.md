# Reproducibility report

Command: `python run.py generate --shipments 1000 --containers 300 --seed 20261022`

The generator was executed twice with seed **20261022** into separate temporary folders. Result: **IDENTICAL**.

| File | Rows (run 1) | Rows (run 2) | MD5 (run 1) | MD5 (run 2) | Match |
|---|---|---|---|---|---|
| ground_truth.csv | 588 | 588 | `9b5c32f93d32c3dcec87cae8c91a13a1` | `9b5c32f93d32c3dcec87cae8c91a13a1` | yes |
| shipment_scenarios.csv | 1,000 | 1,000 | `60870dfe653380e38ba6d5f096169eac` | `60870dfe653380e38ba6d5f096169eac` | yes |
| containers.csv | 300 | 300 | `f81bf9b6fcaacec8779cbf5b7f2c814a` | `f81bf9b6fcaacec8779cbf5b7f2c814a` | yes |
| custody_events.csv | 4,974 | 4,974 | `7e24b489200baf93e397934e4596e8e0` | `7e24b489200baf93e397934e4596e8e0` | yes |
| products.csv | 6 | 6 | `655fe3edc00052e60d3cf1d11745e5d5` | `655fe3edc00052e60d3cf1d11745e5d5` | yes |
| route_stops.csv | 3,487 | 3,487 | `0f53b9297998cb1b9be7a7861312515e` | `0f53b9297998cb1b9be7a7861312515e` | yes |
| sensor_calibrations.csv | 3,050 | 3,050 | `22fc91f8ab8c74743de75efd44cb5725` | `22fc91f8ab8c74743de75efd44cb5725` | yes |
| sensor_readings.csv | 2,027,840 | 2,027,840 | `c24ef92fce1004d7c62380f166f3af96` | `c24ef92fce1004d7c62380f166f3af96` | yes |
| sensors.csv | 600 | 600 | `be14d924f38f768737e27a007bf2c483` | `be14d924f38f768737e27a007bf2c483` | yes |
| shipment_sensor_assignments.csv | 2,000 | 2,000 | `fcaa5fbdf7b646323970e566c8eeffa0` | `fcaa5fbdf7b646323970e566c8eeffa0` | yes |
| shipment_status_events.csv | 4,000 | 4,000 | `89293cc2bd5c969d944452c0e290048b` | `89293cc2bd5c969d944452c0e290048b` | yes |
| shipments.csv | 1,000 | 1,000 | `d158217ff1a37318b9c3de7ce519036f` | `d158217ff1a37318b9c3de7ce519036f` | yes |
| threshold_policies.csv | 12 | 12 | `76ec96606ede13b547ef5cd15948d187` | `76ec96606ede13b547ef5cd15948d187` | yes |

Determinism relies on: one `numpy.random.default_rng(seed)` stream, fixed generation order, sorted outputs, explicit line terminators and no wall-clock values in generated data.
