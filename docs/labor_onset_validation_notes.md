# Labor Onset Validation Notes

## Original Classification Rule

The current primary variable `LABOR_ONSET_GROUP` was created in `scripts/06_policy_calendar_and_analysis_variables.py`.

Original candidate logic:

```text
spontaneous_labor:
  PGADM contains 陣痛, 破水, or 現血

non_spontaneous_or_induction:
  Reason of induction is non-missing
  and PGADM does not contain 陣痛, 破水, or 現血

uncertain:
  all other records
```

This rule is deterministic and reproducible, but it may be too simple for final clinical analysis.

## Sensitivity Classification Rule

The validation script creates `LABOR_ONSET_GROUP_SENSITIVITY` without modifying `LABOR_ONSET_GROUP`.

Sensitivity logic:

```text
spontaneous_labor_strict:
  PGADM contains 陣痛, 破水, or 現血

induction_or_non_spontaneous_strict:
  PGADM does not contain 陣痛, 破水, or 現血
  and Reason of induction is non-missing

uncertain:
  all other records
```

The script also creates:

```text
LABOR_ONSET_VALIDATION_NOTE
FLAG_LABOR_ONSET_REQUIRES_REVIEW
```

Mixed PGADM values containing both labor symptoms and induction terms are kept in the strict spontaneous category by rule, but flagged for review.

## Risk Of Uncertain Equals 0 Percent

An `uncertain` rate of 0 percent does not necessarily mean the classification is clinically complete. It may mean the rules are broad enough to force every record into one of two categories.

This is especially important because `Reason of induction` is used as evidence for non-spontaneous labor, but some reason values may be broad, elective, scheduling-related, or clinically ambiguous.

## Recommended Manual Validation Workflow

1. Review the PGADM value audit and confirm whether each value indicates spontaneous labor, induction, mixed onset, or unclear onset.
2. Review the Reason of induction audit and classify each value as medical indication, elective/scheduling indication, COVID-policy related, or unclear.
3. Review the manual sample in `outputs/28_labor_onset_manual_review_sample.xlsx`.
4. Pay special attention to mixed PGADM values such as values containing both `引產` and `陣痛`.
5. Update classification rules only after clinical or source-database confirmation.

## Modeling Use

Use `LABOR_ONSET_GROUP` as the current primary operational classification only after acknowledging its limitations.

Use `LABOR_ONSET_GROUP_SENSITIVITY` and `FLAG_LABOR_ONSET_REQUIRES_REVIEW` for sensitivity analyses. Recommended sensitivity analyses include:

```text
primary model using LABOR_ONSET_GROUP
model excluding review-required records
model treating mixed onset as spontaneous
model treating mixed onset as non-spontaneous
model with mixed onset as separate category after clinician validation
```

Do not silently drop uncertain or review-required records. Preserve all records and use flags.
