"""Clean the raw export into output/clean/. Never writes to export/.

Every change or flag is logged to output/data_issues.csv.

Usage: python clean.py [export_dir] [output_dir]
"""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

EXPORT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "export")
OUTPUT_DIR = Path(sys.argv[2] if len(sys.argv) > 2 else "output")
CLEAN_DIR = OUTPUT_DIR / "clean"
UNCHANGED_FILES = ["patients.csv", "visits.csv", "prescriptions.csv"]

# Raw test name -> canonical test name.
TEST_NAMES = {
    "HbA1c": "HbA1c",
    "A1C": "HbA1c",
    "Glycated Hb": "HbA1c",
    "FBS": "Fasting Glucose",
    "Glucose (F)": "Fasting Glucose",
    "Fasting Glucose": "Fasting Glucose",
    "PPBS": "Post Prandial Glucose",
    "Glucose (PP)": "Post Prandial Glucose",
    "Post Prandial Glucose": "Post Prandial Glucose",
}

# (canonical test, raw unit) -> (target unit, conversion, decimals).
# HbA1c: IFCC mmol/mol -> NGSP %, master equation % = 0.09148 * mmol/mol + 2.152.
# Glucose: mmol/L -> mg/dL, x 18.016 (molar mass of glucose / 10).
CONVERSIONS = {
    ("HbA1c", "mmol/mol"): ("%", lambda x: 0.09148 * x + 2.152, 1),
    ("Fasting Glucose", "mmol/L"): ("mg/dL", lambda x: x * 18.016, 0),
    ("Post Prandial Glucose", "mmol/L"): ("mg/dL", lambda x: x * 18.016, 0),
}
TARGET_UNITS = {"HbA1c": "%", "Fasting Glucose": "mg/dL",
                "Post Prandial Glucose": "mg/dL"}

DMY_SLASH = re.compile(r"\d{2}/\d{2}/\d{4}")
D_MON_YY = re.compile(r"\d{1,2} [A-Z][a-z]{2} \d{2}")

issues = []


def log(file, row_index, mrn, column, old, new, action, reason):
    issues.append({
        "file": file,
        "line": row_index + 2,  # 1-based, after the header line
        "mrn": mrn,
        "column": column,
        "old_value": old,
        "new_value": new,
        "action": action,
        "reason": reason,
    })


def parse_lab_date(raw):
    """Return YYYY-MM-DD. Only DD/MM/YYYY and 'D Mon YY' are accepted."""
    if DMY_SLASH.fullmatch(raw):
        return datetime.strptime(raw, "%d/%m/%Y").strftime("%Y-%m-%d")
    if D_MON_YY.fullmatch(raw):
        return datetime.strptime(raw, "%d %b %y").strftime("%Y-%m-%d")
    raise ValueError(f"Unrecognised lab date format: {raw!r}")


def fmt(number, decimals):
    return f"{round(number, decimals):.{decimals}f}"


def convert_range(raw, convert, decimals):
    """Convert 'a-b' or '<a' reference ranges; fail loudly on anything else."""
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)", raw):
        low, high = (convert(float(v)) for v in m.groups())
        return f"{fmt(low, decimals)}-{fmt(high, decimals)}"
    if m := re.fullmatch(r"<(\d+(?:\.\d+)?)", raw):
        return f"<{fmt(convert(float(m.group(1))), decimals)}"
    raise ValueError(f"Unrecognised reference range: {raw!r}")


def clean_labs(labs):
    name = "lab_results.csv"
    for col in ["test_name", "value", "unit", "reference_range", "collected_on"]:
        labs[f"raw_{col}"] = labs[col]
    labs["flag"] = ""

    for i, row in labs.iterrows():
        mrn = row["mrn"]

        try:
            parsed = parse_lab_date(row["collected_on"])
        except ValueError as e:
            raise SystemExit(f"{name} line {i + 2} (mrn {mrn}): {e}")
        labs.at[i, "collected_on"] = parsed
        log(name, i, mrn, "collected_on", row["collected_on"], parsed,
            "reformatted", "lab date normalised to YYYY-MM-DD")

        test = TEST_NAMES.get(row["test_name"], row["test_name"])
        if test != row["test_name"]:
            labs.at[i, "test_name"] = test
            log(name, i, mrn, "test_name", row["test_name"], test,
                "renamed", "test name mapped to canonical name")

        unit = row["unit"]
        if unit == "":
            labs.at[i, "flag"] = "missing_unit"
            log(name, i, mrn, "unit", "", "", "flagged",
                "unit missing; value not converted, unit not guessed")
            continue

        if (test, unit) in CONVERSIONS:
            target_unit, convert, decimals = CONVERSIONS[(test, unit)]
            new_value = fmt(convert(float(row["value"])), decimals)
            labs.at[i, "value"] = new_value
            labs.at[i, "unit"] = target_unit
            log(name, i, mrn, "value", row["value"], new_value, "converted",
                f"{unit} -> {target_unit}")
            log(name, i, mrn, "unit", unit, target_unit, "converted",
                f"{unit} -> {target_unit}")
            if row["reference_range"]:
                new_range = convert_range(row["reference_range"], convert, decimals)
                labs.at[i, "reference_range"] = new_range
                log(name, i, mrn, "reference_range", row["reference_range"],
                    new_range, "converted", f"{unit} -> {target_unit}")
        elif test in TARGET_UNITS and unit != TARGET_UNITS[test]:
            raise SystemExit(f"{name} line {i + 2} (mrn {mrn}): no conversion "
                             f"defined for {test} in {unit!r}")
    return labs


def main():
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    labs = pd.read_csv(EXPORT_DIR / "lab_results.csv", dtype=str,
                       keep_default_na=False)
    clean_labs(labs).to_csv(CLEAN_DIR / "lab_results.csv", index=False)

    for name in UNCHANGED_FILES:
        shutil.copyfile(EXPORT_DIR / name, CLEAN_DIR / name)

    pd.DataFrame(issues, columns=["file", "line", "mrn", "column", "old_value",
                                  "new_value", "action", "reason"]
                 ).to_csv(OUTPUT_DIR / "data_issues.csv", index=False)

    summary = pd.DataFrame(issues).groupby(["column", "action"]).size()
    print(f"Wrote {CLEAN_DIR}/ and {OUTPUT_DIR / 'data_issues.csv'} "
          f"({len(issues)} entries)\n{summary.to_string()}")


if __name__ == "__main__":
    main()
