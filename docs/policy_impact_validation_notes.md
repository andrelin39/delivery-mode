# Policy Impact Validation Notes

## Formal Policy Calendar

The formal COVID policy calendar is stored in `docs/policy_calendar_template.csv` and contains three periods:

| policy period | start date | end date | definition |
| --- | --- | --- | --- |
| `pre_policy_period` | dataset earliest `DELIVERY_TIME` | 2021-05-16 | Pre-strict COVID policy period. |
| `strict_covid_policy_period` | 2021-05-17 | 2023-03-19 | New asymptomatic admitted patients and companions required negative RT-PCR within 48 hours before admission or on admission day; companion restrictions; confirmed COVID obstetric patients admitted to negative-pressure or dedicated wards; 2021-05 scheduled 37-38 week admission induction began in response to admission PCR; 2022-07 delivery-room isolation labor room established. |
| `policy_relaxation_period` | 2023-03-20 | dataset latest `DELIVERY_TIME` | COVID policy relaxation; confirmed COVID obstetric patients triaged by severity; mild cases managed with simple isolation in single delivery-room rooms; admission induction returned to physician assessment and recommendation; 2023-04-11 companion rapid-test requirement cancelled. |

In the current v02 dataset, `DELIVERY_TIME` ranges from 2021-08-17 to 2022-12-31. Therefore, all observed records fall within `strict_covid_policy_period`; the pre-policy and relaxation periods have zero observed deliveries in the available analytic window.

## PGADM Final Definition

`LABOR_ONSET_GROUP_FINAL` is derived from `PGADM` using the confirmed clinical definition:

| source value | final group |
| --- | --- |
| `PGADM = 0` or contains `引產` | `non_spontaneous_or_induction` |
| `PGADM = 1` or contains `陣痛`, `破水`, or `現血` | `spontaneous_labor` |

If `PGADM` contains both induction and labor-sign terms, the record is classified as `non_spontaneous_or_induction` and `FLAG_LABOR_ONSET_REQUIRES_REVIEW = 1`.

Lineage is retained in `LABOR_ONSET_GROUP_FINAL_LINEAGE`.

## DELIVER_MODE Final Definition

`DELIVERY_MODE_GROUP_FINAL` is derived from `DELIVER_MODE` using the confirmed codebook:

| source value | final group |
| --- | --- |
| `0` or `C/S` | `CS` |
| `1` or `NSD` | `NSD` |
| `2` or `VED` | `VED` |
| `3` or `VBAC` | `VBAC` |

Derived binary outcomes:

| variable | definition |
| --- | --- |
| `CS_BINARY_FINAL` | `CS = 1`; `NSD`, `VED`, `VBAC = 0` |
| `OPERATIVE_DELIVERY_BINARY_FINAL` | `CS` or `VED = 1`; `NSD` or `VBAC = 0` |
| `VAGINAL_BIRTH_BINARY_FINAL` | `NSD`, `VED`, or `VBAC = 1`; `CS = 0` |

Lineage is retained in the corresponding `_LINEAGE` variables.

## COVID_POLICY_PERIOD_FINAL Definition

`DELIVERY_DATE_FINAL` is derived from `DELIVERY_TIME` only. `DELIVERY_TIME.1` is retained in the dataset but is not used for analysis linkage.

`COVID_POLICY_PERIOD_FINAL` is assigned by linking `DELIVERY_DATE_FINAL` to the formal policy calendar. Lineage is retained in `COVID_POLICY_PERIOD_FINAL_LINEAGE`.

## Policy Validation Purpose

The validation outputs assess whether delivery timing across formal policy periods is associated with:

- `PGADM`
- `LABOR_ONSET_GROUP_FINAL`
- `DELIVERY_MODE_GROUP_FINAL`
- CS, VED, NSD, operative delivery, and vaginal birth indicators

This is a policy-period association validation step. It is intended to describe observed distributions and identify whether policy-period variables should be included in subsequent modeling.

## Causal Interpretation Warning

These outputs do not support direct causal claims. Policy periods may be confounded by calendar time, patient mix, clinical practice changes, staffing, institutional workflow, SARS-CoV-2 prevalence, and other unmeasured temporal factors. Formal causal interpretation would require additional design assumptions and model specification.

## Next Modeling Plan

Recommended next steps:

1. Treat `COVID_POLICY_PERIOD_FINAL` as a temporal policy-period covariate only if future or expanded data include records outside the strict policy period.
2. Use `LABOR_ONSET_GROUP_FINAL` as the primary labor-onset variable, with sensitivity analyses excluding records where `FLAG_LABOR_ONSET_REQUIRES_REVIEW = 1`.
3. Model `CS_BINARY_FINAL` as the primary delivery outcome.
4. Consider `OPERATIVE_DELIVERY_BINARY_FINAL` as a secondary outcome because VED is common in this dataset.
5. If VBAC remains sparse, retain it in descriptive tables but combine with other vaginal births for binary outcomes.
6. Adjust formal models for clinically relevant covariates such as maternal age, BMI, parity, gestational age, birth weight, and labor duration variables when temporally appropriate.
