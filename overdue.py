"""Work out each patient's follow-up due date and whether they are overdue.

Rules (as chosen; values are passed in, never defaulted here):
  due date = next_appointment on the person's last visit
             else an interval parsed from the last visit's note ("review 6 wks",
             "r/v 3/12", "review tomorrow", "rpt yearly", ...)
             else last visit date + DEFAULT days
  overdue  = due date + GRACE days < AS_OF
             and no visit (by any MRN in a linked duplicate pair) after the due date

A "person" is one MRN, or both MRNs of a pair in output/possible_duplicates.csv.
Only visits on or before AS_OF are used. The rule that set the due date is
recorded. Notes saying the patient died or transferred care are flagged in
`status_flag`; nobody is dropped. This does not filter to diabetic patients.

Reads output/clean/visits.csv, output/clean/patients.csv,
output/possible_duplicates.csv. Writes output/overdue.csv (one row per person
with at least one visit).

Usage: python overdue.py --as-of YYYY-MM-DD --grace-days N --default-days N [--output-dir output]
"""
import argparse
import re
from pathlib import Path

import pandas as pd

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
STATUS_PATTERNS = {
    "deceased": re.compile(r"\bexpired\b|could not be revived|death summary",
                           re.IGNORECASE),
    "transferred": re.compile(r"relocat|transfer(?:red)? (?:of )?care|"
                              r"transfer summary", re.IGNORECASE),
}


def parse_interval(note):
    """Return (pd.DateOffset, matched text) for the first interval found, else None."""
    found = []
    for pattern in INTERVAL_PATTERNS:
        for m in pattern.finditer(note):
            found.append(m)
    if not found:
        return None
    m = min(found, key=lambda m: m.start())
    groups = [g.lower() for g in m.groups()]
    if groups[0] == "tomorrow":
        return pd.DateOffset(days=1), m.group(0)
    if groups[0] == "yearly":
        return pd.DateOffset(years=1), m.group(0)
    n = int(groups[0])
    unit = groups[1]
    if unit in ("12",) or unit.startswith("m"):
        return pd.DateOffset(months=n), m.group(0)
    if unit in ("52",) or unit.startswith("w"):
        return pd.DateOffset(weeks=n), m.group(0)
    if unit in ("7",) or unit.startswith("d"):
        return pd.DateOffset(days=n), m.group(0)
    return pd.DateOffset(years=n), m.group(0)


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
    parser.add_argument("--default-days", required=True, type=int)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args()

    out = Path(args.output_dir)
    as_of = to_date(args.as_of, "--as-of")
    grace = pd.Timedelta(days=args.grace_days)
    default = pd.Timedelta(days=args.default_days)

    read = lambda p: pd.read_csv(p, dtype=str, keep_default_na=False)
    visits = read(out / "clean" / "visits.csv")
    patients = read(out / "clean" / "patients.csv")
    pairs = read(out / "possible_duplicates.csv")

    person_of = {row["mrn_b"]: row["mrn_a"] for _, row in pairs.iterrows()}
    visits["person"] = visits["mrn"].map(lambda m: person_of.get(m, m))
    visits["date"] = [to_date(d, f"visits {v}")
                      for d, v in zip(visits["visit_date"], visits["visit_id"])]
    visits = visits[visits["date"] <= as_of]

    mrns_of = visits.groupby("person")["mrn"].agg(lambda s: " + ".join(sorted(set(s))))
    names = patients.set_index("mrn")[["name", "phone"]]

    rows = []
    for person, pv in visits.sort_values(["date", "visit_id"]).groupby("person"):
        last = pv.iloc[-1]
        if last["next_appointment"]:
            due = to_date(last["next_appointment"], f"visits {last['visit_id']}")
            rule, detail = "next_appointment", last["next_appointment"]
        elif (parsed := parse_interval(last["notes"])) is not None:
            offset, detail = parsed
            due = last["date"] + offset
            rule = "note_interval"
        else:
            due = last["date"] + default
            rule, detail = "default", f"{args.default_days} days"

        after_due = pv[pv["date"] > due]
        statuses = sorted({s for note in pv["notes"]
                           for s, pat in STATUS_PATTERNS.items() if pat.search(note)})
        rows.append({
            "mrns": mrns_of[person],
            "name": names.at[person, "name"] if person in names.index else "",
            "phone": names.at[person, "phone"] if person in names.index else "",
            "last_visit_id": last["visit_id"],
            "last_visit_date": last["visit_date"],
            "last_visit_department": last["department"],
            "due_date": due.strftime("%Y-%m-%d"),
            "due_rule": rule,
            "due_detail": detail,
            "visits_after_due": len(after_due),
            "days_past_due": (as_of - due).days,
            "overdue": bool(due + grace < as_of and after_due.empty),
            "status_flag": " + ".join(statuses),
        })

    result = pd.DataFrame(rows)
    result.to_csv(out / "overdue.csv", index=False)

    print(f"AS_OF={args.as_of} GRACE={args.grace_days}d DEFAULT={args.default_days}d")
    print(f"{len(result)} people with visits -> {out / 'overdue.csv'}")
    print(result.groupby(["due_rule", "overdue"]).size().to_string())
    flagged = result[result["status_flag"] != ""]
    print(f"\nStatus flags from notes ({len(flagged)}):")
    print(flagged[["mrns", "name", "status_flag", "overdue"]].to_string(index=False))


if __name__ == "__main__":
    main()
