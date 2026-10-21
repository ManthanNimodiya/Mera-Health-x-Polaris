"""Read-only report on the raw hospital export. Cleans nothing, writes nothing.

Usage: python explore.py [export_dir]
"""
import re
import sys
from pathlib import Path

import pandas as pd

EXPORT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "export")
FILES = ["patients.csv", "visits.csv", "prescriptions.csv", "lab_results.csv"]
DATE_COLUMNS = {
    "patients.csv": ["dob", "registered_on"],
    "visits.csv": ["visit_date", "next_appointment"],
    "prescriptions.csv": ["prescribed_on"],
    "lab_results.csv": ["collected_on"],
}
NULL_LIKE = {"na", "n/a", "nan", "null", "none", "-", "--", "nil", "?"}
MAX_LISTED = 25


def read(name):
    # Everything as strings; empty cells stay "" so nothing is converted or hidden.
    return pd.read_csv(EXPORT_DIR / name, dtype=str, keep_default_na=False)


def header(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def shape(value):
    """Describe a value's shape: digits -> 9, letters -> A, other chars kept."""
    return re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", value))


def report_columns(name, df):
    header(f"{name}: {len(df)} rows, {len(df.columns)} columns")
    for col in df.columns:
        s = df[col]
        empty = (s == "").sum()
        blank = ((s != "") & (s.str.strip() == "")).sum()
        null_like = s.str.strip().str.lower().isin(NULL_LIKE).sum()
        padded = ((s != s.str.strip()) & (s.str.strip() != "")).sum()
        uniques = s.value_counts()
        print(f"\n  {col}: empty={empty} whitespace-only={blank} "
              f"null-like-text={null_like} leading/trailing-space={padded} "
              f"unique={len(uniques)}")
        if len(uniques) <= MAX_LISTED:
            for value, count in uniques.items():
                print(f"      {value!r}: {count}")


def report_dates(name, df):
    for col in DATE_COLUMNS[name]:
        values = df[col][df[col].str.strip() != ""]
        shapes = values.groupby(values.map(shape))
        print(f"\n  {name}.{col}: {len(shapes)} format shape(s)")
        for fmt, group in sorted(shapes, key=lambda g: -len(g[1])):
            examples = ", ".join(repr(v) for v in group.unique()[:4])
            print(f"      {fmt!r:22} x{len(group):<4} e.g. {examples}")


def report_shared(patients, col):
    values = patients[patients[col].str.strip() != ""]
    groups = values.groupby(col).filter(lambda g: len(g) > 1).groupby(col)
    print(f"\n  Patients sharing {col}: {groups.ngroups} value(s)")
    for value, group in groups:
        print(f"    {value!r}:")
        for _, row in group.iterrows():
            print(f"        {row['mrn']}  {row['name']!r}  dob={row['dob']!r} "
                  f"sex={row['sex']!r} phone={row['phone']!r}")


def main():
    data = {name: read(name) for name in FILES}

    for name, df in data.items():
        report_columns(name, df)

    header("Date formats found (shape: 9=digit, A=letter)")
    for name, df in data.items():
        report_dates(name, df)

    labs = data["lab_results.csv"]
    combos = labs.groupby(["test_name", "unit"]).size()
    header(f"lab_results test_name / unit combinations ({len(combos)})")
    for (test, unit), count in combos.items():
        print(f"  {test!r:28} {unit!r:16} x{count}")

    drugs = data["prescriptions.csv"]["drug"].value_counts().sort_index()
    header(f"prescriptions drug names ({len(drugs)} distinct, exact strings)")
    for drug, count in drugs.items():
        print(f"  {drug!r}: {count}")

    header("Patients sharing phone or DOB")
    for col in ["phone", "dob"]:
        report_shared(data["patients.csv"], col)


if __name__ == "__main__":
    main()
