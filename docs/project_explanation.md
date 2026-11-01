# Cold Chain Monitoring: what we did and how

## The problem
Some products, like vaccines, must stay inside a temperature range while they are stored and moved. For example, 2°C to 8°C. If the temperature goes outside that range, that is called an excursion. A company needs to know when it happened, how long it lasted, who had the shipment at that time, and what was done about it.

The assignment asked us to build a working system for this, using synthetic (made-up) data, and to prove that it works.

## What we built
1. **A data generator.** It creates 1,000 shipments, 300 containers and about 2 million sensor readings (one every 5 minutes, for trips of 2 to 5 days). It uses a fixed seed, 20261022, so it gives the same data every time.
2. **A database.** The data is stored in tables with primary keys and foreign keys. We used SQLite by default, and it can also run on MySQL.
3. **A monitoring engine.** This is the main part. It reads the sensor data and finds the problems.
4. **An API and a dashboard.** FastAPI gives access to the data, and Streamlit shows it in the browser.
5. **Checks and reports.** We validate the data and compare the engine's results with the correct answers.

## How the data is made
We first create the normal data: products, limits for each product, containers, sensors, shipments, route stops and normal readings. After that we add problems on purpose and write each one in a separate file called the ground truth. The ground truth is the list of correct answers. The engine never reads it.

The problems we add include short and long excursions, missing readings, sensors with expired calibration, late-arriving readings and delayed shipments. We also add the five special cases from the assignment:
- a reading that is impossible, like 150°C
- missing readings that someone could wrongly take as "safe"
- a shipment delivered before it left
- a shipment given the limits of a different product
- an excursion whose duration is easy to count wrong

## How the engine decides
- A reading exactly on the limit is fine. Only values beyond the limit count as outside.
- An excursion starts at the first reading outside the range and ends at the first reading back inside. The duration is the time between these two, not the number of readings multiplied by five. This matters when some readings are missing in the middle.
- Each product has a time it is allowed to stay outside the range. If the excursion is not longer than that, we record it but no action is needed. If it is longer, it is an actionable excursion, and we create a notification and a corrective action.
- Missing readings are never treated as safe. We record them as a gap and mark that time as unverified.
- Impossible readings are kept in the data but flagged, and they are not used to decide excursions.
- Limits can change over time. The engine uses the limits that were valid at the time of each reading.
- If a shipment has the wrong product's limits, we flag it and still check its readings against the correct limits.
- Status changes (for example a corrective action going from OPEN to ASSIGNED to IN_PROGRESS to RESOLVED to VERIFIED) are saved as new records. Nothing is overwritten, and steps cannot be skipped.

## How we checked it
- **Validation:** 85 checks, covering unique IDs, valid links between tables, allowed values, date order, totals that add up, status order and duplicates. All 85 pass on the full data.
- **Evaluation:** we compared what the engine found with the ground truth. On the full data it found all 192 temperature excursions, all 65 humidity excursions and all 137 gaps, with no false alarms. Durations matched exactly.
- **Reproducibility:** we ran the generator twice with the same seed. The row counts and file checksums were the same.
- **Tests:** 16 small tests, including damaged copies of the data (wrong order, duplicates, missing links) to confirm the checks catch the errors.

Getting 100% on the evaluation does not mean the system would be 100% accurate on real sensor data. The data is synthetic and follows the same rules the engine uses. The result shows the engine does what we documented.

One bug we found this way: our generator sometimes gave a shipment its own product's limits when it was supposed to give the wrong ones. The evaluation showed one missed case, and we fixed the generator.

## What is not done
- No login or user roles.
- No live sensor connection. All data is generated.
- All shipments end as delivered, so there are no shipments still in transit.
- The dashboard and API were checked by running them by hand, not with automated tests.
- The MySQL option was not tested by us. SQLite was used for the full run.

## How to run
```
pip install -r requirements.txt
python run.py all
uvicorn coldchain.api:app
streamlit run dashboard.py
```
The `README.md` has the details, and the other files in the `docs` folder have the full reports.
