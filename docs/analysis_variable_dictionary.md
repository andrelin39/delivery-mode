# Analysis Variable Dictionary

## DELIVERY_DATE_FINAL

`DELIVERY_DATE_FINAL` is derived from `DELIVERY_TIME`. If `DELIVERY_TIME` is missing, `DELIVERY_TIME.1` is used as a fallback.

The original `DELIVERY_TIME` and `DELIVERY_TIME.1` columns are preserved. Existing `FLAG_DELIVERY_TIME_CONFLICT` is also preserved and should be used in sensitivity analysis.

## LABOR_ONSET_GROUP

`LABOR_ONSET_GROUP` is a preliminary operational variable for spontaneous versus non-spontaneous labor.

Current candidate rules:

```text
spontaneous_labor:
  PGADM contains 陣痛, 破水, or 現血

non_spontaneous_or_induction:
  Reason of induction is non-missing
  and PGADM does not contain 陣痛, 破水, or 現血

uncertain:
  all other records
```

Supporting fields:

```text
LABOR_ONSET_RULE_SOURCE
FLAG_LABOR_ONSET_UNCERTAIN
```

This variable is preliminary and requires clinician or source-database validation before final analysis.

## DELIVERY_MODE_GROUP

`DELIVERY_MODE_GROUP` maps the observed `DELIVER_MODE` values into analysis labels:

```text
NSD -> NSD
VED -> VED
C/S -> CS
other values -> other_or_uncertain
```

No unknown values are forcibly recoded. The mapping report is written to `outputs/23_delivery_mode_mapping_report.xlsx`.

## COVID_POLICY_PERIOD

`COVID_POLICY_PERIOD` is assigned by linking `DELIVERY_DATE_FINAL` to the external policy calendar in:

```text
docs/policy_calendar_template.csv
```

The template currently contains placeholder rows only. Because no confirmed policy dates are entered yet, `COVID_POLICY_PERIOD` remains missing for all records.

Policy period assignment must be based on external hospital policy dates, not inferred from outcome distributions.

## Pending Confirmation

Items requiring manual confirmation:

```text
confirmed hospital policy start and end dates
whether DELIVERY_TIME is the correct policy-linkage date
whether DELIVERY_TIME.1 should ever override DELIVERY_TIME
clinical validity of PGADM terms as labor-onset indicators
whether Reason of induction should define non-spontaneous labor
official DELIVER_MODE codebook and final outcome grouping
```
