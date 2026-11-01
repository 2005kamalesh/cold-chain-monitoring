# Cold Chain Monitoring and Excursion Management

This project watches temperature and humidity readings for shipments, finds excursions (readings outside a product's allowed range), finds missing readings, and keeps a record of notifications and corrective actions. All data is synthetic.

- **Fixed seed:** 20261022
- **Full size:** 1,000 shipments, 300 containers, about 2 million readings (every 5 minutes, trips of 2 to 5 days)
- **Generator command:** `python run.py generate --shipments 1000 --containers 300 --seed 20261022`

## What you need
- Python 3.10 or newer
- MySQL is optional. The default database is SQLite, which needs no setup.

## Setup
Open a terminal in the project folder (the one that contains `run.py`).

Windows:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
Linux or macOS:
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Step 1: Generate the data and run the monitoring
```
python run.py all
```
This takes about 2 minutes on SQLite. It does these steps in order:
1. generates the data and the ground truth file
2. loads it into the database
3. runs the monitoring engine
4. runs the 85 validation checks
5. compares the engine's results with the ground truth

For a quick test with less data, use `python run.py all --shipments 100 --containers 30`.

You can also run each step alone: `generate`, `load`, `monitor`, `validate`, `evaluate`.

The data is stored in `cold_chain.db` (created in the project folder). The generated CSV files are in `data/raw/`. The ground truth is in `data/ground_truth/`. The validation and evaluation reports are written to `docs/`.

## Step 2: Start the application
Use two terminals. In both, activate the virtual environment first (see Setup).

1.Terminal 1, the API:
======================

uvicorn coldchain.api:app


2.Terminal 2, the dashboard:
============================

streamlit run dashboard.py

Open http://localhost:8501 in the browser. The API documentation is at http://localhost:8000/docs. The API must be running before you open the dashboard.

In the dashboard, shipments that are fully compliant have no excursions, gaps or issues. To see those, use the Compliance filter on the Shipment monitoring page and choose a status other than COMPLIANT.

## Check the results
```
python run.py reproduce              # runs the generator twice with the same seed and compares checksums
python tests/test_engine.py          # unit tests for the detection logic
python tests/test_negative_cases.py  # tests with damaged data (needs data/raw from Step 1)
```
`pytest -q` runs the same tests if pytest is installed.

## Export the data (CSV, JSON, SQL)
```
python run.py export
```
This writes `seed_data.sql` and JSON files to `data/exports/`. At full size they are large (about 0.9 GB). A small example (20 shipments) is already in `data/sample/`.

## Use MySQL instead of SQLite
1. In MySQL, create an empty database: `CREATE DATABASE cold_chain;`
2. Install the driver: `pip install pymysql`
3. Set the database address in every terminal before running any command:

Windows PowerShell:
```
$env:DATABASE_URL="mysql://root:yourpassword@localhost:3306/cold_chain"
```
Windows cmd:
```
set DATABASE_URL=mysql://root:yourpassword@localhost:3306/cold_chain
```
Linux or macOS:
```
export DATABASE_URL="mysql://root:yourpassword@localhost:3306/cold_chain"
```
4. Run the same commands as above. Try `--shipments 100 --containers 30` first, because loading into MySQL is slower than SQLite.

Running `load` deletes and recreates the tables in that database. If a special character in the password causes a problem, write it as a code (`@` as `%40`, `#` as `%23`). The MySQL option was not tested by the author; the full run was done on SQLite.

## Folder guide
| Folder or file | What it is |
|---|---|
| `run.py` | Runs all the commands above |
| `coldchain/` | The code: generator, monitoring engine, validation, API |
| `dashboard.py` | The Streamlit dashboard |
| `tests/` | The tests |
| `data/raw/`, `data/ground_truth/` | Generated data and the correct answers used for evaluation |
| `data/sample/` | A small example with CSV, SQL and JSON |
| `docs/` | Data dictionary, database diagram, business rules, validation report, evaluation report, test case list, reproducibility report, source manifest, project explanation |
