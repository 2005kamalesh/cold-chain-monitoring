# Assumptions, decisions, trade-offs and limitations

## The problem
Watch temperature and humidity readings from sensors on shipments, find when a product left its allowed range, find when readings are missing, and keep records of who was told and what was done. Show that the results are correct using generated data with known answers.

## Assumptions
| Topic | What I assumed |
|---|---|
| Product limits | Example values (for instance 2 to 8 C) are made up for the exercise, not real pharmaceutical limits |
| Limits at the edge | A reading exactly equal to a limit is inside the range |
| Excursion start and end | Starts at the first reading outside the range and ends at the first later reading inside it. If no later reading exists, it ends five minutes after the last bad reading |
| Allowed excursion time | Counted in one stretch (not added up over the trip). Action is needed only when the duration is longer than the allowed time, not equal |
| Severity | LOW if within the allowed time, MEDIUM up to twice the allowed time, HIGH above that |
| Missing readings | The time is "unverified", never safe. A gap is reported if the time between two readings is more than 15 minutes |
| Impossible readings | Below -50 or above 60 C, and outside 0 to 100 percent humidity. They are kept, flagged and not used for excursions |
| Late readings | More than 30 minutes between measurement and arrival |
| Late shipment | Delivered more than 60 minutes after the plan |
| Policy changes | A new policy starts on 15 Sept 2026 and shortens the allowed time by 5 minutes. Each reading uses the policy valid at its own time |
| Containers | One container per shipment, with 12 hours between uses, never two shipments at once. Two sensors per container (temperature and humidity) |

## Decisions and trade-offs
| Decision | Why | Cost |
|---|---|---|
| SQLite by default, MySQL by setting `DATABASE_URL` | Anyone can run it with no setup, and the assignment allows free local services | MySQL is supported by the same code but I could not test it |
| A small database layer written with `sqlite3` and `pymysql` instead of SQLAlchemy | The build environment could not install SQLAlchemy, and it means fewer dependencies | SQL is written by hand and only uses features common to both databases |
| Generator and engine kept separate, with the ground truth in its own file | The engine must find problems from the data, not read the answers | Expected results are worked out twice (once by the generator, once by the engine), which is more code |
| Ground truth comes from the injection settings and the written rules | The assignment says labels must come from documented rules, not random choice | If a rule is misunderstood, both sides could be wrong the same way |
| Excursion duration from timestamps | Counting readings gives the wrong answer when readings are missing inside an excursion | None significant |
| pandas for the full 2 million readings | Fast enough (about 2 minutes end to end) | Needs a few GB of memory at full size |
| Floats stored as DOUBLE, not DECIMAL | Simpler and portable | Not ideal for money, fine for sensor values |
| Evaluation counted per injected problem | One problem is one item, so scores are easy to read | Not the same as counting every reading |

## How I know it works
- 85 validation checks pass on the full data (`validation_report.md`).
- The engine's results match the ground truth for every problem type (`evaluation_report.md`). Perfect scores here mean the engine follows the written rules on synthetic data. They do not show how it would perform on real sensor data.
- Unit tests use the examples from the assignment, such as a 15 minute excursion and the 20 minute undercount case.
- Tests with damaged copies of the data prove the checks catch wrong order, duplicates, missing links and a skipped lifecycle step.
- Two runs with the same seed give identical files (`reproducibility_report.md`).

## Differences from the assignment, and limits
- The full dataset is too large for normal GitHub files, so the 2 million row readings file and the SQL seed are in `data/full/` as compressed files. The README shows how to regenerate everything.
- Temperature and humidity excursions that overlap in time are checked on each sensor separately, but this case was not injected on purpose.
- All shipments end as delivered. There is no shipment still in transit.
- Running `python run.py monitor` (or `all`) rebuilds the engine's tables. Corrective actions added through the API are lost if the monitor step is run again. Re-running it is only meant for fresh data.
- No login or user roles, and no live sensor connection.
- The dashboard and API have no automated tests. I checked them by hand.

## Next steps if I had more time
Keep corrective actions across engine runs, add login and roles, add a test run on MySQL, add tests for the dashboard, and add shipments that are still in transit.
