"""Hand-written list of diabetes drugs seen in prescriptions.csv.

Matching is exact on a normalised name (dosage-form prefix stripped,
lowercased), never by substring: "Adapalene gel" contains "dapa" but is an
acne gel, not Dapagliflozin.

Usage: python drugs.py [prescriptions.csv]   # prints how each drug name is classified
"""
import re
import sys

import pandas as pd

# Generic names (after normalise()) that are diabetes medications.
DIABETES_DRUGS = {
    # Biguanide
    "metformin",
    "metformin sr",
    # Sulfonylureas
    "glimepiride",
    "glimepiride + metformin",
    "gliclazide mr",
    # DPP-4 inhibitors
    "sitagliptin",
    "vildagliptin",
    # SGLT2 inhibitor (also used for heart failure / CKD without diabetes)
    "dapagliflozin",
    # Alpha-glucosidase inhibitor
    "voglibose",
    # Insulins
    "human mixtard 30/70",
    "insulin aspart",
    "insulin glargine",
    "insulin degludec",
    "insulin lispro",
}

# Checked by hand and deliberately not diabetes drugs.
NOT_DIABETES_DRUGS = {
    "adapalene gel",  # topical retinoid for acne
}

PREFIX = re.compile(r"^(t\.|tab\.?|inj\.|syp)\s+", re.IGNORECASE)


def normalise(drug):
    """'Tab. Metformin SR' / 'T. Metformin SR' / 'TAB METFORMIN SR' -> 'metformin sr'."""
    return PREFIX.sub("", drug.strip()).lower()


def is_diabetes_drug(drug):
    return normalise(drug) in DIABETES_DRUGS


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "export/prescriptions.csv"
    drugs = pd.read_csv(path, dtype=str, keep_default_na=False)["drug"]
    for drug, count in drugs.value_counts().sort_index().items():
        mark = "DIABETES" if is_diabetes_drug(drug) else "-"
        print(f"{mark:9} {drug!r} x{count}")
