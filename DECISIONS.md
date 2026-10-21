# DECISIONS

## Diabetic definition (my choice)
- Diabetic = diabetes drug AND (note OR HbA1c >= 6.5 OR Diabetology visit). PCOS-only metformin excluded.
- Count (verified by running evidence.py / duplicates.py / overdue.py):
  - 87 records meet the diabetic rule (drug AND note/HbA1c>=6.5/Diabetology)
  - 86 people - Joseph Dsouza / Joseph D'Souza (SVH027863/SVH029322) counted once, flagged as possible duplicate
  - 85 - GDM patient SVH027966 moved to doctor review, not called
  - 79 - 6 patients died or transferred care (see below)
- Doctor review, not called: HbA1c >= 6.5 only (9, some had a high result and no follow-up), HbA1c with no unit (values 65-68, likely mmol/mol), GDM, prediabetes/IGT, drug-only
- HbA1c >= 6.5 cutoff: ADA Standards of Care (Section 2, Diagnosis and Classification of Diabetes, Table 2.1: https://diabetesjournals.org/care/article/49/Supplement_1/S27/163926/2-Diagnosis-and-Classification-of-Diabetes)

## Not called: died / transferred
| MRN | Visit | Date | Status | Note |
|---|---|---|---|---|
| SVH025339 | V042478 | 2025-03-21 | died | "Attender came for records. Informed pt expired at home last month. File closed" |
| SVH026086 | V042492 | 2025-04-04 | died | "adm with sepsis, DKA; shifted to ICU; pt expired on 4/4/2025; death summary given to attenders" |
| SVH025698 | V042743 | 2025-10-10 | died | "brought with chest pain, sweating x 2 hrs. ECG: ant wall STEMI. sudden collapse, CPR x 30 min, could not be revived. declared expired 5:40 am" |
| SVH024860 | V042727 | 2025-09-24 | transferred | "Relocated to Hyderabad. Transfer of care letter issued. To f/u with local physician, records handed over." |
| SVH025512 | V042828 | 2025-12-03 | transferred | "came for transfer summary; will continue f/u near native place; transferred care to another hospital" |
| SVH028346 | V042950 | 2026-02-10 | transferred | "Review. FBS 104. BP 131/82. Adv diet + daily walk. r/v 3/12. Pt relocating to Pune with son. Transferred care to another hospital, summary and reports given." |

## Duplicates
- 4 pairs flagged, not merged. Linked for the "visited since?" check (Padma Reddy visited Jul 2026 under the other record)
- 3 shared phones - front desk asks for the patient by name

## Overdue definition (my choice)
Numbers below: the 79 people, AS_OF 2026-09-29, linked duplicate pairs counted as one person.

- **Diabetes-related visit** = Diabetology, OR a diabetes drug prescribed at that visit (by visit_id), OR the note mentions diabetes / HbA1c / sugars / FBS / PPBS / GRBS / RBS or "F # / PP #" readings.
  - Without GRBS/RBS and "F # / PP #", 3 clear diabetes follow-ups (SVH025331, SVH025948, SVH026465) were missed: 9 people had a non-diabetes last visit instead of 6.
- **Option B:** due date from the last diabetes-related visit; only a later diabetes-related visit counts as followed up. Reason: a dental/ENT/skin visit doesn't check diabetes.
  - Overdue: B = 41. (Hospital question 3 still open - option A, where any later visit counts, would give 35. The old rule, last visit of any kind, gave 36.)
  - The 6 who are overdue under B but not A: SVH026153 (later ENT), SVH026193 (later Dental), SVH027082 + SVH030772 (later thyroid visit), SVH027261 (later Dermatology), SVH027925 + SVH029107 (later Orthopaedics), SVH029007 (see below).
- **Due date:** next_appointment on that visit > interval in its note ("review 6 wks", "r/v 3/12", "rpt HbA1c 3 months") > DEFAULT. Lab repeats count only for diabetes tests (HbA1c/FBS/PPBS); "rpt TSH 6 wks" is ignored.
- **DEFAULT 3 months, GRACE 14 days.** ADA: HbA1c every 3 months if not at target, twice a year if stable (Standards of Care, Section 6, Glycemic Goals: https://diabetesjournals.org/care/article/49/Supplement_1/S132/163927). DEFAULT 6 months would change only 2 people (SVH029625, SVH029767): 41 -> 39.
- **SVH029007:** kept on the list, flagged "last visit 'dose stepped up' may be a diabetes visit - overdue either way". Last visit 2026-01-26 General Medicine: "Routine f/u. Dose stepped up. Review after 3 months"; no diabetes drug or reading recorded at that visit.
