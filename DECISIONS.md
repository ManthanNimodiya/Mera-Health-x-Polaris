# DECISIONS

## 1. Terms I had to define

**As-of date.** Passed in (`--as-of 2026-09-29`, the export's last date), never today's date, so the same export always gives the same list.

**Diabetic** = on a diabetes drug AND at least one of: a note saying diabetic, HbA1c >= 6.5 %, a Diabetology visit. Gestational diabetes (GDM, diabetes in pregnancy) and metformin for PCOS do not count. *Why:* a drug alone isn't proof (metformin is also used for PCOS); a lab result alone has no treating doctor behind it. 87 records -> 86 people (one duplicate pair) -> 85 (GDM moved to doctor review) -> 79 (6 died or transferred).
*Leaves out:* diet-only diabetics. *Wrongly includes:* data-entry errors in notes or prescriptions.

**Diabetes-related visit** = Diabetology, OR a diabetes drug prescribed at that visit, OR the note mentions diabetes / HbA1c / sugars / FBS / PPBS / GRBS / RBS / "F # / PP #". *Why:* a dental, ENT or skin visit doesn't check diabetes. *Misses:* a diabetes visit written without these words (SVH029007, flagged).

**Follow-up / due date** = from the last diabetes-related visit: its next_appointment, else the interval in its note ("review 6 wks", "r/v 3/12"), else 3 months. Lab repeats count only for HbA1c/FBS/PPBS ("rpt TSH 6 wks" is ignored). *Why 3 months:* ADA advises HbA1c every 3 months if not at target, twice a year if stable; I took the cautious end.

**Overdue** = due date + 14 days grace is before the as-of date, AND no later diabetes-related visit (under either record of a duplicate pair). Result: 41. If any later visit counted, it would be 35; with a 6-month default, 39. *Wrongly includes:* patients followed up elsewhere or by phone.

## 2. Data problems and what I did
Every change is logged in `output/data_issues.csv`; nothing dropped or merged.

- **Lab dates in 3 formats** (`03/04/2024`, `14 Oct 23`, `2 Oct 23`). For the slash dates, 238 have a first number > 12 and none a second number > 12, so they are DD/MM. All converted to YYYY-MM-DD; any other format stops the script.
- **Two lab dates after the export end** (2026-12-19 and 2027-02-27, SVH027355 and SVH030138). Not fixed; SVH027355 (on the call list) is flagged "lab result dated after export end - check". Neither patient's status depends on them.
- **HbA1c under 3 names** (HbA1c, A1C, Glycated Hb); Glycated Hb in mmol/mol converted to %: % = 0.09148 x mmol/mol + 2.152 (NGSP).
- **Glucose under several names** (FBS, Glucose (F), PPBS...) and some in mmol/L; converted to mg/dL (x 18, standard mmol/L -> mg/dL factor, from glucose molar mass 180 g/mol).
- **12 lab rows with no unit**, including 3 HbA1c of 65-68 (probably mmol/mol). Flagged, not converted or guessed.
- **Drug name variants** ("Metformin", "T. Metformin", "Tab. Metformin"): prefixes stripped, matched exactly against a hand-written list. Exact matching keeps "Adapalene gel" (acne) out; "Human Mixtard" (insulin) is in.
- **Duplicate patients:** 4 pairs with the same date of birth, same phone and a similar name (e.g. "Md. Rafiq" / "Mohammed Rafiq"). Linked, not merged; Padma Reddy's July 2026 visit is under her second record.
- **Shared phones:** 3 numbers with 3 people each. **Missing phones:** 8 patients, 3 on the call list.
- **Died / transferred** is only in visit notes (3 each). Moved to "Not called" with the note quoted.
- **Metformin for PCOS/PCOD** (4) and **GDM** (3) found in notes; excluded from "diabetic".

## 3. Flagged for a person instead of decided
- **Doctor review, do not call yet (16):** HbA1c >= 6.5 with no diabetes drug or note (8), HbA1c with no unit (2), GDM (3), prediabetes/IGT (3).
- **Duplicate pairs:** shown on the list with the other record number; the hospital should merge them.
- **SVH029007:** last visit "Dose stepped up. Review after 3 months" may be a diabetes visit. Overdue either way.
- **HbA1c without units:** on the review list, and flagged on the call list for one patient.
- **Shared phones:** front desk asks for the patient by name before giving the reason.

## 4. What this can't be trusted for
- Deaths or transfers not written in a visit note: such patients would still be called.
- Patients treated at another hospital or clinic.
- Diagnoses never recorded here; anything after 2026-09-29.
- Notes are searched by keywords; unusual wording or spelling can be missed.
- The 3-month default and 14-day grace are my choices, not the hospital's.
- The 5 questions I sent to the hospital are still unanswered (question -> what I assumed -> what changes if the answer differs):
  1. Only confirmed diabetics, or also prediabetes and pregnancy diabetes? -> Confirmed only; GDM and prediabetes go to doctor review. -> If included, those 6 move from doctor review to the call list (if overdue).
  2. Default return interval and grace when no date is set? -> 3 months, 14 days. -> 6 months gives 39 instead of 41; other values change the count.
  3. Does any visit count as follow-up, or only diabetes visits? -> Diabetes visits only (option B). -> Any visit gives 35 instead of 41.
  4. How will the front desk use the list, and who should never be called? -> Printable HTML/CSV; died/transferred found in notes excluded. -> Other exclusions (e.g. a do-not-call list) would need that data; a different format is a small change.
  5. Duplicates and shared phones: show once or separately? -> Duplicates shown once, flagged with the other record; shared phones flagged. -> Separately would list 3 pairs as 6 rows and risk two calls to one person.

## What I looked up
- ADA Standards of Care 2026, Section 2 (HbA1c >= 6.5 % for diagnosis): https://diabetesjournals.org/care/article/49/Supplement_1/S27/163926/2-Diagnosis-and-Classification-of-Diabetes
- ADA Standards of Care 2026, Section 6 (HbA1c testing frequency): https://diabetesjournals.org/care/article/49/Supplement_1/S132/163927
- HbA1c mmol/mol to % conversion (NGSP): https://ngsp.org/ifccngsp.asp
- Glucose mmol/L to mg/dL: x 18 (standard mmol/L -> mg/dL factor, from glucose molar mass 180 g/mol).
- Medical shorthand: "r/v 3/12" = review in 3 months; "x 2/52" = for 2 weeks (symptom duration); GRBS = home blood sugar; F/PP = fasting / after-meal sugar; IGT = impaired glucose tolerance.

## Where I disagreed with the agent / what it caught
- **It caught:** my diabetes-visit definition missed GRBS and "F # / PP #" readings, so 3 real diabetes follow-ups looked like non-diabetes visits.
- **It caught:** my first count of 81 didn't match my own rule (87); that led to the 87 -> 86 -> 85 -> 79 chain.
- **It caught:** I called the 3 shared phones "family phones", but one number has 3 women with different surnames, so I changed the wording.
