# Diabetes follow-up call list

Builds a list of diabetic patients who are overdue for follow-up, for the front desk to call, from the raw hospital export in `export/`.

## Requirements
- Python 3.10+
- pandas (`pip install pandas`)

## Run
Run everything from the repo folder (the scripts use relative paths like `export/` and `output/`):

```bash
cd Mera-Health-x-Polaris
python3 -m venv .venv
source .venv/bin/activate
pip install pandas
python run.py --as-of 2026-09-29
```

Then open `output/call_list.html` (the same list is in `output/call_list.csv`).

`--as-of` is the date the list is calculated for; the scripts never use today's date.

## What each script does
- `run.py` - runs the four steps below in order, then writes `output/call_list.csv` and `output/call_list.html`.
- `clean.py` - normalises lab dates, test names and units into `output/clean/`; logs every change to `output/data_issues.csv`.
- `evidence.py` - lists every piece of diabetes evidence per patient (drug, note, HbA1c >= 6.5, Diabetology visit) with its source.
- `duplicates.py` - flags possible duplicate patients (same DOB + phone + similar name) and shared phone numbers; merges nothing.
- `overdue.py` - works out each patient's diabetes follow-up due date and whether they are overdue.
- `drugs.py` - the hand-written list of diabetes drugs (used by the scripts above).
- `explore.py` - optional read-only report on the raw CSVs; not part of the run.

`export/` is never modified. All output goes to `output/` (not committed).

## Definitions
What counts as "diabetic", "diabetes-related visit", "due date" and "overdue", and why, is in `DECISIONS.md`. Data findings are in `NOTES.md`.
