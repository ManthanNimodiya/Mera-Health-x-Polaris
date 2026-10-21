# NOTES

## Metformin / insulin are not proof of diabetes
Some diabetes drugs in `export/prescriptions.csv` are given for other reasons (found in `export/visits.csv` notes, all OBG / Dr. Kavya Menon):

- **PCOS on metformin:** SVH025191, SVH029693, SVH030554, SVH028876 (written as "PCOD", HbA1c 5.4). Metformin for PCOS, not diabetes.
- **GDM (gestational diabetes):** SVH027966 (metformin), SVH028326 (insulin), SVH028068 (diet only). Pregnancy-only diabetes; may resolve after delivery.
- Related, no drug: SVH028864 "IGT" and SVH024742 "Prediabetes - HbA1c 6.2".

A drug-only rule for "diabetic" would wrongly include the PCOS patients and would count GDM patients as diabetic. Whether GDM / prediabetes count is still an open question for the hospital (see PLAN.md).

## Dapagliflozin
Dapagliflozin is in `drugs.py` but is also prescribed for heart failure and CKD in people without diabetes. A patient on dapagliflozin alone may not be diabetic; check notes / HbA1c before counting them.

## Shared phone 9000043929 may not be a family
`duplicates.py` lists three phones shared by different people. Two look like families (the Mullas on 9000032917; A. Farzana / Nasreen A Ali / Nazeer A on 9000090725). But 9000043929 is shared by three women with three different surnames, born 1947, 1974 and 2003:

- SVH029084 Meena P (1947-04-04)
- SVH026167 Revathi Pandian (1974-10-08)
- SVH030711 Shanthi Biradar (2003-03-13)

Could be a family, a neighbour's or carer's phone, or a data-entry error. Don't assume "family"; the front desk should confirm who they are reaching before discussing anything clinical on this number.
