# NOTES

## Metformin / insulin are not proof of diabetes
Some diabetes drugs in `export/prescriptions.csv` are given for other reasons (found in `export/visits.csv` notes, all OBG / Dr. Kavya Menon):

- **PCOS on metformin:** SVH025191, SVH029693, SVH030554. Metformin for PCOS, not diabetes.
- **GDM (gestational diabetes):** SVH027966 (metformin), SVH028326 (insulin), SVH028068 (diet only). Pregnancy-only diabetes; may resolve after delivery.
- Related, no drug: SVH028864 "IGT" and SVH024742 "Prediabetes - HbA1c 6.2".

A drug-only rule for "diabetic" would wrongly include the PCOS patients and would count GDM patients as diabetic. Whether GDM / prediabetes count is still an open question for the hospital (see PLAN.md).

## Dapagliflozin
Dapagliflozin is in `drugs.py` but is also prescribed for heart failure and CKD in people without diabetes. A patient on dapagliflozin alone may not be diabetic; check notes / HbA1c before counting them.
