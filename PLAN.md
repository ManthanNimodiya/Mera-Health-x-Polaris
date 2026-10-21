# PLAN

Meenakshi wants a list of diabetic patients who are overdue for follow-up so the front desk can call them. Problem is "diabetic" and "overdue" aren't defined, and the data is messy.

## steps
1. look through the csvs first, see what's broken
2. clean dates / test names / drug names, log every change
3. figure out who's diabetic (meds, notes, HbA1c)
4. figure out who's overdue (next appt date > notes like "review 6 wks" > some default)
5. output a simple csv/html list with a reason for each patient
6. manually check some patients
7. write DECISIONS.md and reply.txt

## things i noticed
- dates in different formats
- HbA1c has 3 names and one uses a different unit
- some patients look duplicated, some have the same name but aren't the same person
- missing/shared phone numbers

## not sure about
- does prediabetes or pregnancy diabetes count?
- what if there's no follow-up date?
- does any visit count as follow-up?
(asked the hospital, will go with my best guess till they reply)

## rules for myself
- no ML, just simple rules
- don't delete or merge anything silently
- use a fixed date, not today
