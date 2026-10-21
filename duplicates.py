"""Flag patients that may be the same person, and phones shared by families.

Flags only; never merges or drops anything.

A pair is a possible duplicate only if ALL of these hold:
  - same dob
  - same phone (non-empty)
  - similar name (token rule below)
Same name with a different dob or phone is treated as a different person.

Token rule for "similar name": lowercase, remove dots and apostrophes, split
into words. Similar if every word of the shorter name matches a different
word of the longer name, where two words match if they are equal, one is a
prefix of the other (padma / padmavathi), or they are a hand-listed
abbreviation (md = mohammed).

Reads output/clean/patients.csv. Writes output/possible_duplicates.csv and
output/shared_phones.csv.

Usage: python duplicates.py [output_dir]
"""
import re
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd

OUTPUT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "output")
ABBREVIATIONS = {"md": "mohammed"}


def words(name):
    cleaned = re.sub(r"[.']", "", name.lower())
    return [ABBREVIATIONS.get(w, w) for w in cleaned.split()]


def words_match(a, b):
    return a.startswith(b) or b.startswith(a)


def similar_names(name_a, name_b):
    short, long = sorted([words(name_a), words(name_b)], key=len)
    remaining = list(long)
    for w in short:
        match = next((r for r in remaining if words_match(w, r)), None)
        if match is None:
            return False
        remaining.remove(match)
    return True


def main():
    patients = pd.read_csv(OUTPUT_DIR / "clean" / "patients.csv", dtype=str,
                           keep_default_na=False)
    with_phone = patients[patients["phone"] != ""]

    pairs = []
    for (dob, phone), group in with_phone.groupby(["dob", "phone"]):
        for (_, a), (_, b) in combinations(group.iterrows(), 2):
            if similar_names(a["name"], b["name"]):
                pairs.append({
                    "mrn_a": a["mrn"], "mrn_b": b["mrn"],
                    "names": f"{a['name']} | {b['name']}",
                    "dob": dob, "phone": phone,
                    "reason": "same dob, same phone, similar name (token rule)",
                })
            else:
                print(f"NOTE: same dob+phone but names not similar, not flagged: "
                      f"{a['mrn']} {a['name']!r} / {b['mrn']} {b['name']!r}")
    duplicates = pd.DataFrame(pairs, columns=["mrn_a", "mrn_b", "names", "dob",
                                              "phone", "reason"])

    # A phone is "shared" if it still covers more than one person after
    # treating each possible-duplicate pair as one person.
    same_person = {row["mrn_b"]: row["mrn_a"] for _, row in duplicates.iterrows()}
    people = with_phone.assign(person=with_phone["mrn"].map(
        lambda m: same_person.get(m, m)))
    people_per_phone = people.groupby("phone")["person"].nunique()
    shared_phones = people_per_phone[people_per_phone > 1].index
    shared = (people[people["phone"].isin(shared_phones)]
              .assign(people_on_phone=lambda d: d["phone"].map(people_per_phone))
              [["phone", "people_on_phone", "mrn", "name", "dob", "sex"]]
              .sort_values(["phone", "dob"]))

    duplicates.to_csv(OUTPUT_DIR / "possible_duplicates.csv", index=False)
    shared.to_csv(OUTPUT_DIR / "shared_phones.csv", index=False)

    print(f"\nPossible duplicates ({len(duplicates)} pairs) -> "
          f"{OUTPUT_DIR / 'possible_duplicates.csv'}")
    print(duplicates.to_string(index=False))
    print(f"\nShared phones, not duplicate pairs ({len(shared_phones)} phones) -> "
          f"{OUTPUT_DIR / 'shared_phones.csv'}")
    print(shared.to_string(index=False))
    print(f"\n({(patients['phone'] == '').sum()} patients have no phone and were "
          f"not compared.)")


if __name__ == "__main__":
    main()
