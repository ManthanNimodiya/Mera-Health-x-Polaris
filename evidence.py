"""List every piece of diabetes evidence per patient, with its source.

Does NOT decide who is diabetic. It only collects evidence:
  drug          - a diabetes drug from drugs.py was prescribed
  note          - a visit note mentions diabetes about the patient
  hba1c_ge_6_5  - a lab HbA1c (in %, after clean.py) is >= 6.5
  diabetology   - the patient had a Diabetology visit
Note mentions that are NOT about the patient having diabetes are kept as
separate context types (never counted as evidence):
  note_negated     - "non-diabetic", "no h/o diabetes", "denies diabetes"
  note_family      - "family history of diabetes", "father diabetic"
  note_gdm         - gestational diabetes / GDM
  note_prediabetes - prediabetes / pre-diabetic / IGT
  hba1c_no_unit    - HbA1c row with no unit (value not interpreted)

Reads output/clean/ (run clean.py first). Writes:
  output/diabetes_evidence.csv             one row per piece of evidence
  output/diabetes_evidence_by_patient.csv  one row per patient
and prints counts per combination of evidence types.

Usage: python evidence.py [output_dir]
"""
import re
import sys
from pathlib import Path

import pandas as pd

from drugs import is_diabetes_drug

OUTPUT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "output")
CLEAN_DIR = OUTPUT_DIR / "clean"
EVIDENCE = ["drug", "note", "hba1c_ge_6_5", "diabetology"]
CONTEXT = ["note_negated", "note_family", "note_gdm", "note_prediabetes",
           "hba1c_no_unit"]

TERM = re.compile(
    r"\b(pre-?diabet\w*|diabet\w*|t[12]dm|dm2|dm|niddm|iddm|gdm|igt)\b",
    re.IGNORECASE)
FAMILY = re.compile(r"\b(family|f/h|father|mother|parents?|brother|sister)\b",
                    re.IGNORECASE)
NEGATION = re.compile(r"\b(non|no|not|denies|nil)\b", re.IGNORECASE)
CLAUSE_BREAK = re.compile(r"[;.]")


def read(name):
    return pd.read_csv(CLEAN_DIR / name, dtype=str, keep_default_na=False)


def classify(notes, match):
    """Classify one diabetes term in a note by the clause text before it."""
    term = match.group(1).lower()
    before = CLAUSE_BREAK.split(notes[:match.start()])[-1]
    if term.startswith("pre") or term == "igt":
        return "note_prediabetes"
    if term == "gdm" or "gestational" in before.lower():
        return "note_gdm"
    if FAMILY.search(before):
        return "note_family"
    if NEGATION.search(before):
        return "note_negated"
    return "note"


def collect():
    rows = []

    def add(mrn, kind, source, source_id, date, detail):
        rows.append({"mrn": mrn, "type": kind, "source": source,
                     "source_id": source_id, "date": date, "detail": detail})

    for _, p in read("prescriptions.csv").iterrows():
        if is_diabetes_drug(p["drug"]):
            add(p["mrn"], "drug", "prescriptions.csv", p["visit_id"],
                p["prescribed_on"], f"{p['drug']} {p['dose']}")

    for _, v in read("visits.csv").iterrows():
        if v["department"] == "Diabetology":
            add(v["mrn"], "diabetology", "visits.csv", v["visit_id"],
                v["visit_date"], v["doctor"])
        seen = set()
        for m in TERM.finditer(v["notes"]):
            kind = classify(v["notes"], m)
            if kind not in seen:
                seen.add(kind)
                add(v["mrn"], kind, "visits.csv", v["visit_id"],
                    v["visit_date"], v["notes"])

    labs = read("lab_results.csv")
    for i, lab in labs[labs["test_name"] == "HbA1c"].iterrows():
        source_id = f"line {i + 2}"
        if lab["unit"] == "":
            add(lab["mrn"], "hba1c_no_unit", "lab_results.csv", source_id,
                lab["collected_on"], f"HbA1c {lab['value']} (no unit)")
        elif lab["unit"] != "%":
            raise SystemExit(f"Unexpected HbA1c unit {lab['unit']!r} at {source_id}")
        elif float(lab["value"]) >= 6.5:
            add(lab["mrn"], "hba1c_ge_6_5", "lab_results.csv", source_id,
                lab["collected_on"], f"HbA1c {lab['value']} %")

    return pd.DataFrame(rows, columns=["mrn", "type", "source", "source_id",
                                       "date", "detail"])


def main():
    evidence = collect().sort_values(["mrn", "type", "date"])
    patients = read("patients.csv")[["mrn", "name"]]

    unknown = sorted(set(evidence["mrn"]) - set(patients["mrn"]))
    if unknown:
        print(f"WARNING: evidence for MRNs not in patients.csv: {unknown}")

    counts = evidence.pivot_table(index="mrn", columns="type", values="source",
                                  aggfunc="count", fill_value=0)
    counts = counts.reindex(columns=EVIDENCE + CONTEXT, fill_value=0)
    by_patient = patients.merge(counts, left_on="mrn", right_index=True,
                                how="left").fillna(0)
    by_patient[EVIDENCE + CONTEXT] = by_patient[EVIDENCE + CONTEXT].astype(int)
    by_patient["evidence"] = by_patient[EVIDENCE].apply(
        lambda r: " + ".join(t for t in EVIDENCE if r[t]) or "none", axis=1)
    by_patient["context"] = by_patient[CONTEXT].apply(
        lambda r: " + ".join(t for t in CONTEXT if r[t]), axis=1)

    evidence.to_csv(OUTPUT_DIR / "diabetes_evidence.csv", index=False)
    by_patient.to_csv(OUTPUT_DIR / "diabetes_evidence_by_patient.csv", index=False)

    print(f"{len(evidence)} evidence rows for {evidence['mrn'].nunique()} patients\n")
    print("Patients per evidence combination:")
    print(by_patient["evidence"].value_counts().to_string())
    print("\nPatients with context-only note/lab findings, by evidence combination:")
    with_context = by_patient[by_patient["context"] != ""]
    print(with_context.groupby(["context", "evidence"]).size().to_string())


if __name__ == "__main__":
    main()
