"""Run the whole pipeline and write the front-desk call list.

  python run.py --as-of 2026-09-29

Steps: clean.py -> evidence.py -> duplicates.py -> overdue.py, then builds
  output/call_list.csv   overdue diabetic patients, most days overdue first
  output/call_list.html  same list + "Doctor review - do not call yet" + "Not called"

Definitions are in DECISIONS.md. Nothing in export/ is touched.
"""
import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

from overdue import STATUS_PATTERNS

OUT = Path("output")
GRACE_DAYS = 14
DEFAULT_MONTHS = 3
EVIDENCE = ["drug", "note", "hba1c_ge_6_5", "diabetology"]
LABELS = {"drug": "diabetes drug", "note": "note says diabetic",
          "hba1c_ge_6_5": "HbA1c >= 6.5", "diabetology": "Diabetology visit"}
# Hand-written flags from DECISIONS.md.
MANUAL_FLAGS = {
    "SVH029007": "last visit 'dose stepped up' may be a diabetes visit - overdue either way",
}
PCOS = re.compile(r"\bPCO[SD]\b|polycystic", re.IGNORECASE)


def step(*args):
    print(f"\n$ python {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, *args], check=True)


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def table(df):
    head = "".join(f"<th>{html.escape(c)}</th>" for c in df.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row) + "</tr>"
        for row in df.itertuples(index=False))
    return f"<table><tr>{head}</tr>{body}</table>"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    as_of = args.as_of

    step("clean.py")
    step("evidence.py")
    step("duplicates.py")
    step("overdue.py", "--as-of", as_of, "--grace-days", str(GRACE_DAYS),
         "--default-months", str(DEFAULT_MONTHS))

    patients = read(OUT / "clean" / "patients.csv").set_index("mrn")
    visits = read(OUT / "clean" / "visits.csv")
    by_patient = read(OUT / "diabetes_evidence_by_patient.csv")
    evidence = read(OUT / "diabetes_evidence.csv")
    pairs = read(OUT / "possible_duplicates.csv")
    shared = read(OUT / "shared_phones.csv")
    overdue = read(OUT / "overdue.csv").set_index("person")

    person_of = dict(zip(pairs["mrn_b"], pairs["mrn_a"]))
    other_mrn = {**dict(zip(pairs["mrn_a"], pairs["mrn_b"])),
                 **dict(zip(pairs["mrn_b"], pairs["mrn_a"]))}
    for df in (by_patient, evidence, visits):
        df["person"] = df["mrn"].map(lambda m: person_of.get(m, m))
    counts = {c: by_patient[c].astype(int) > 0 for c in by_patient.columns
              if c not in ("mrn", "name", "evidence", "context", "person")}
    flags = pd.DataFrame(counts).groupby(by_patient["person"]).any()

    # Count chain.
    meets_rule = (by_patient["drug"].astype(int) > 0) & (
        by_patient[["note", "hba1c_ge_6_5", "diabetology"]].astype(int).gt(0).any(axis=1))
    records = int(meets_rule.sum())
    people = set(by_patient.loc[meets_rule, "person"])
    gdm = {p for p in people if flags.at[p, "note_gdm"]}
    after_gdm = people - gdm
    visits_to_date = visits[visits["visit_date"] <= as_of]
    not_called = visits_to_date[visits_to_date["notes"].map(
        lambda n: any(p.search(n) for p in STATUS_PATTERNS.values()))]
    gone = set(not_called["person"])
    diabetic = after_gdm - gone
    on_list = [p for p in diabetic if p in overdue.index
               and overdue.at[p, "overdue"] == "True"]
    chain = [("records meet the diabetic rule", records),
             ("people (duplicate pairs counted once)", len(people)),
             ("after moving GDM to doctor review", len(after_gdm)),
             ("after removing died / transferred", len(diabetic)),
             ("overdue - to call", len(on_list))]

    # Section 1: call list.
    labs = read(OUT / "clean" / "lab_results.csv")
    future_lab_people = {person_of.get(m, m)
                         for m in labs.loc[labs["collected_on"] > as_of, "mrn"]}
    shared_count = shared.groupby("phone")["people_on_phone"].first()
    rows = []
    for p in on_list:
        o = overdue.loc[p]
        phone = patients.at[p, "phone"]
        row_flags = []
        if p in other_mrn:
            row_flags.append(f"possible duplicate: also {other_mrn[p]} "
                             f"({patients.at[other_mrn[p], 'name']})")
        if phone == "":
            row_flags.append("no phone")
        elif phone in shared_count.index:
            row_flags.append(f"shared phone ({shared_count[phone]} people)")
        if p in future_lab_people:
            row_flags.append("lab result dated after export end - check")
        if flags.at[p, "hba1c_no_unit"]:
            row_flags.append("HbA1c with no unit on file")
        if p in MANUAL_FLAGS:
            row_flags.append(MANUAL_FLAGS[p])
        rule = o["due_rule"].replace("_", " ")
        rows.append({
            "name": patients.at[p, "name"],
            "mrn": o["mrns"],
            "phone": phone,
            "last_diabetes_visit_date": o["last_diabetes_visit_date"],
            "last_diabetes_visit_dept": o["last_diabetes_visit_department"],
            "last_diabetes_visit_doctor": o["last_diabetes_visit_doctor"],
            "due_date": o["due_date"],
            "due_date_set_by": f"{rule}: {o['due_detail']}",
            "days_overdue": int(o["days_past_due"]),
            "why_diabetic": " + ".join(LABELS[e] for e in EVIDENCE if flags.at[p, e]),
            "flags": "; ".join(row_flags),
        })
    call_list = pd.DataFrame(rows).sort_values(["days_overdue", "name"],
                                               ascending=[False, True])
    call_list.to_csv(OUT / "call_list.csv", index=False)

    # Section 2: doctor review - not diabetic by the rule (or GDM), not gone.
    review_rows = []
    pcos_rows = []
    for p in sorted((set(flags.index) - after_gdm) - gone):
        f = flags.loc[p]
        ev = evidence[evidence["person"] == p]
        detail = lambda t: ", ".join(dict.fromkeys(ev.loc[ev["type"] == t, "detail"]))
        reasons = []
        has = [e for e in EVIDENCE if f[e]]
        if has == ["hba1c_ge_6_5"]:
            reasons.append(f"HbA1c >= 6.5 only ({detail('hba1c_ge_6_5')})")
        if has == ["drug"]:
            drugs = ", ".join(dict.fromkeys(ev.loc[ev["type"] == "drug", "detail"]
                                            .str.replace(r"\s+\d.*$", "", regex=True)))
            pcos = visits[(visits["person"] == p) & visits["notes"].str.contains(PCOS)]
            if len(pcos) and not (f["hba1c_no_unit"] or f["note_gdm"]
                                  or f["note_prediabetes"]):
                last = pcos.sort_values("visit_date").iloc[-1]
                pcos_rows.append({"name": patients.at[p, "name"], "mrn": p,
                                  "status": "metformin for PCOS/PCOD, not diabetes",
                                  "visit": f"{last['visit_id']} {last['visit_date']}",
                                  "note": f'"{last["notes"]}"'})
                continue
            reasons.append(f"diabetes drug only ({drugs})")
        if f["hba1c_no_unit"]:
            reasons.append(f"HbA1c with no unit ({detail('hba1c_no_unit')})")
        if f["note_gdm"]:
            reasons.append("GDM (diabetes in pregnancy)")
        if f["note_prediabetes"]:
            reasons.append("prediabetes / IGT")
        if reasons:
            mrns = " + ".join(sorted(by_patient.loc[by_patient["person"] == p, "mrn"]))
            review_rows.append({"name": patients.at[p, "name"], "mrn": mrns,
                                "reason": "; ".join(reasons)})
    review = pd.DataFrame(review_rows, columns=["name", "mrn", "reason"])

    # Section 3: not called.
    gone_rows = pd.DataFrame({
        "name": [patients.at[m, "name"] for m in not_called["mrn"]],
        "mrn": not_called["mrn"],
        "status": [" + ".join(s for s, pat in STATUS_PATTERNS.items() if pat.search(n))
                   for n in not_called["notes"]],
        "visit": not_called["visit_id"] + " " + not_called["visit_date"],
        "note": '"' + not_called["notes"] + '"',
    })
    gone_rows = pd.concat([gone_rows, pd.DataFrame(pcos_rows)], ignore_index=True)

    chain_html = "".join(f"<li>{n} {html.escape(label)}</li>" for label, n in chain)
    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Diabetes follow-up call list</title>
<style>table {{border-collapse: collapse}} td, th {{border: 1px solid #999; padding: 4px; text-align: left; vertical-align: top}}</style>
</head><body>
<h1>Diabetes follow-up call list</h1>
<p>As of {html.escape(as_of)}. Grace {GRACE_DAYS} days; default follow-up {DEFAULT_MONTHS} months. Definitions: DECISIONS.md.</p>
<ul>{chain_html}</ul>
<p><strong>Ask for the patient by name before giving the reason for the call.</strong></p>
<h2>1. Call list ({len(call_list)})</h2>
{table(call_list)}
<h2>2. Doctor review - do not call yet ({len(review)})</h2>
{table(review)}
<h2>3. Not called ({len(gone_rows)})</h2>
{table(gone_rows)}
</body></html>
"""
    (OUT / "call_list.html").write_text(page, encoding="utf-8")

    print("\nCount chain:")
    for label, n in chain:
        print(f"  {n:4}  {label}")
    print(f"\nSections: call list {len(call_list)}, doctor review {len(review)}, "
          f"not called {len(gone_rows)}")
    print(f"Wrote {OUT / 'call_list.csv'} and {OUT / 'call_list.html'}")


if __name__ == "__main__":
    main()
