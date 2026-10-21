"""Work out each patient's diabetes follow-up due date and whether they are overdue.

Rules (see DECISIONS.md):
  diabetes-related visit = Diabetology, OR a diabetes drug prescribed at that
      visit, OR the note mentions diabetes / HbA1c / sugars / FBS / PPBS /
      GRBS / RBS or "F # / PP #" readings
  due date = on the person's LAST diabetes-related visit:
             next_appointment
             else an interval parsed from its note ("review 6 wks", "r/v 3/12",
                  "review tomorrow", "rpt HbA1c 3 months", ...); lab repeats
                  count only for HbA1c/FBS/PPBS ("rpt TSH 6 wks" is ignored)
             else visit date + DEFAULT months
  overdue  = due date + GRACE days < AS_OF
             and no diabetes-related visit (by any MRN in a linked duplicate
             pair) after the due date

A "person" is one MRN, or both MRNs of a pair in output/possible_duplicates.csv.
Only visits on or before AS_OF are used. The rule that set the due date is
recorded. Notes saying the patient died or transferred care are flagged in
`status_flag`; nobody is dropped. People with no diabetes-related visit get no
row. This does not filter to diabetic patients.

Reads output/clean/{visits,patients,prescriptions}.csv and
output/possible_duplicates.csv. Writes output/overdue.csv.

Usage: python overdue.py --as-of YYYY-MM-DD --grace-days N --default-months N [--output-dir output]
"""
import argparse
import re
from pathlib import Path

import pandas as pd

from drugs import is_diabetes_drug
from evidence import TERM, classify

UNIT = r"(day|days|d|wk|wks|week|weeks|month|months|mth|mths|yr|yrs|year|years)"
INTERVAL_PATTERNS = [
    # "review 6 wks", "Review after 3 months", "rpt after 1 wk",
    # "Rpt HbA1c 6 months", "Rpt TSH 6 wks", "r/v 3 days if fever persists"
    re.compile(r"\b(?:review|r/v|rpt)\b(?:\s+[a-z0-9/]+?)??\s+(?:after\s+|in\s+)?"
               rf"(\d+)\s*{UNIT}\b", re.IGNORECASE),
    # "r/v 3/12" = 3 months, "r/v 2/52" = 2 weeks, "r/v 5/7" = 5 days
    re.compile(r"\b(?:review|r/v|rpt)\s+(\d+)/(12|52|7)\b", re.IGNORECASE),
    re.compile(r"\b(?:review|r/v|rpt)\s+(tomorrow|yearly)\b", re.IGNORECASE),
]
# "rpt <test> ..." where <test> is not a diabetes test is not a follow-up date.
LAB_REPEAT = re.compile(r"^rpt\s+(?!after\b|\d)(\S+)", re.IGNORECASE)
DIABETES_LAB_TESTS = {"hba1c", "fbs", "ppbs", "fbs/ppbs"}
DIABETES_WORDS = re.compile(
    r"\b(hba1c|sugars?|fbs|ppbs|grbs|rbs)\b|\bF \d+ / PP \d+", re.IGNORECASE)
STATUS_PATTERNS = {
    "deceased": re.compile(r"\bexpired\b|could not be revived|death summary",
                           re.IGNORECASE),
    "transferred": re.compile(r"relocat|transfer(?:red)? (?:of )?care|"
                              r"transfer summary", re.IGNORECASE),
}


def parse_interval(note):
    """Return (pd.DateOffset, matched text) for the first usable interval, else None."""
    found = sorted((m for p in INTERVAL_PATTERNS for m in p.finditer(note)),
                   key=lambda m: m.start())
    for m in found:
        lab = LAB_REPEAT.match(m.group(0))
        if lab and lab.group(1).lower() not in DIABETES_LAB_TESTS:
            continue
        groups = [g.lower() for g in m.groups()]
        if groups[0] == "tomorrow":
            return pd.DateOffset(days=1), m.group(0)
        if groups[0] == "yearly":
            return pd.DateOffset(years=1), m.group(0)
        n, unit = int(groups[0]), groups[1]
        if unit == "12" or unit.startswith("m"):
            return pd.DateOffset(months=n), m.group(0)
        if unit == "52" or unit.startswith("w"):
            return pd.DateOffset(weeks=n), m.group(0)
        if unit == "7" or unit.startswith("d"):
            return pd.DateOffset(days=n), m.group(0)
        return pd.DateOffset(years=n), m.group(0)
    return None


def mentions_diabetes(note):
    if DIABETES_WORDS.search(note):
        return True
    return any(classify(note, m) == "note" for m in TERM.finditer(note))


def to_date(value, where):
    try:
        return pd.Timestamp(pd.to_datetime(value, format="%Y-%m-%d"))
    except ValueError:
        raise SystemExit(f"Bad date {value!r} in {where}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--grace-days", required=True, type=int)
    parser.add_argument("--default-months", required=True, type=int)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    out = Path(args.output_dir)
    as_of = to_date(args.as_of, "--as-of")
    grace = pd.Timedelta(days=args.grace_days)
    default = pd.DateOffset(months=args.default_months)

    read = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)
    visits = read(out / "clean" / "visits.csv")
    patients = read(out / "clean" / "patients.csv")
    prescriptions = read(out / "clean" / "prescriptions.csv")
    pairs = read(out / "possible_duplicates.csv")

    person_of = {row["mrn_b"]: row["mrn_a"] for _, row in pairs.iterrows()}
    visits["person"] = visits["mrn"].map(lambda m: person_of.get(m, m))
    visits["date"] = [to_date(d, f"visits {v}")
                      for d, v in zip(visits["visit_date"], visits["visit_id"])]
    visits = visits[visits["date"] <= as_of]
    drug_visits = set(prescriptions.loc[prescriptions["drug"].map(is_diabetes_drug),
                                        "visit_id"])
    visits["diabetes_visit"] = ((visits["department"] == "Diabetology")
                                | visits["visit_id"].isin(drug_visits)
                                | visits["notes"].map(mentions_diabetes))

    mrns_of = visits.groupby("person")["mrn"].agg(lambda s: " + ".join(sorted(set(s))))
    names = patients.set_index("mrn")[["name", "phone"]]

    rows = []
    for person, pv in visits.sort_values(["date", "visit_id"]).groupby("person"):
        diabetes_visits = pv[pv["diabetes_visit"]]
        if diabetes_visits.empty:
            continue
        last = diabetes_visits.iloc[-1]
        if last["next_appointment"]:
            due = to_date(last["next_appointment"], f"visits {last['visit_id']}")
            rule, detail = "next_appointment", last["next_appointment"]
        elif (parsed := parse_interval(last["notes"])) is not None:
            offset, detail = parsed
            due = last["date"] + offset
            rule = "note_interval"
        else:
            due = last["date"] + default
            rule, detail = "default", f"{args.default_months} months"

        after_due = diabetes_visits[diabetes_visits["date"] > due]
        later = pv[pv["date"] > last["date"]]
        statuses = sorted({s for note in pv["notes"]
                           for s, pat in STATUS_PATTERNS.items() if pat.search(note)})
        rows.append({
            "person": person,
            "mrns": mrns_of[person],
            "name": names.at[person, "name"] if person in names.index else "",
            "phone": names.at[person, "phone"] if person in names.index else "",
            "last_diabetes_visit_id": last["visit_id"],
            "last_diabetes_visit_date": last["visit_date"],
            "last_diabetes_visit_department": last["department"],
            "last_diabetes_visit_doctor": last["doctor"],
            "due_date": due.strftime("%Y-%m-%d"),
            "due_rule": rule,
            "due_detail": detail,
            "diabetes_visits_after_due": len(after_due),
            "later_other_visits": "; ".join(
                f"{v.visit_date} {v.department}"
                for v in later[~later["diabetes_visit"]].itertuples()),
            "days_past_due": (as_of - due).days,
            "overdue": bool(due + grace < as_of and after_due.empty),
            "status_flag": " + ".join(statuses),
        })

    result = pd.DataFrame(rows)
    result.to_csv(out / "overdue.csv", index=False)

    print(f"AS_OF={args.as_of} GRACE={args.grace_days}d DEFAULT={args.default_months} months")
    print(f"{len(result)} people with a diabetes-related visit -> {out / 'overdue.csv'}")
    print(result.groupby(["due_rule", "overdue"]).size().to_string())


if __name__ == "__main__":
    main()
