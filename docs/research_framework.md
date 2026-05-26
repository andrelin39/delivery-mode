# COVID Policy And Delivery Outcome Research Framework

## Study Rationale

This project should be framed around how COVID-related hospital policy changes may have altered admission and labor management processes, and how those process changes may have influenced delivery outcomes. The central question is not simply whether delivery mode differs by patient characteristics. The core question is whether a policy environment changed the clinical pathway leading to delivery outcomes.

## COVID Policy As Natural Experiment

COVID-related hospital policies can be conceptualized as an external exposure if policy timing was determined by hospital, regional, or national infection-control requirements rather than by individual patient delivery risk. This makes the policy period a potential natural experiment.

The exposure should be defined using external institutional policy dates whenever possible. Calendar date alone is not sufficient unless it can be linked to specific policy changes such as admission screening, companion restrictions, induction scheduling, labor room capacity, epidural workflow, or cesarean decision processes.

## Spontaneous Labor Vs Non-Spontaneous Labor Concept

The distinction between spontaneous labor and non-spontaneous labor is a key stratification concept. Patients presenting with labor symptoms may be affected differently by COVID admission policies than patients admitted for induction or planned delivery.

Candidate spontaneous labor indicators include admission terms such as `陣痛`, `破水`, and `現血` in `PGADM`. Candidate non-spontaneous or induction indicators include `引產` in `PGADM` and non-missing `Reason of induction`. Mixed values should be treated as uncertain or analyzed as a separate subgroup until clinically validated.

## Hypothesized Mechanism

COVID policy changes may alter:

1. Timing of hospital admission.
2. Threshold for induction or admission.
3. Labor monitoring and intervention patterns.
4. Epidural timing or availability.
5. Decision-making threshold for assisted vaginal delivery or cesarean delivery.

These mechanisms may affect delivery mode, labor duration, epidural use, and neonatal outcomes.

## Exposure-Outcome Structure

Primary exposure:

```text
COVID policy period
```

The policy period should be derived from external hospital policy dates and linked to `DELIVERY_TIME`.

Primary outcome:

```text
DELIVER_MODE
```

Delivery mode should be treated as an outcome, not as the primary exposure.

## Possible Mediators

Potential mediators include:

```text
EPA timing
EPA time
PAIN
PROC_TPALE4A
DRUG_MTMPS
DRUG_MIOXY
STAGE1_MINS
STAGE2_MINS_CLEAN
```

These variables may lie on the pathway between COVID policy and delivery outcome, so they should not be automatically adjusted for in a primary total-effect model.

## Possible Confounders

Potential confounders include:

```text
Age
BMI
GRAVIDA
PARA
GESTAT_WEEKS_DECIMAL
EDUCATION
MARRIAGE
PGADM
Reason of induction
DIAG_2
DIAG_3
DIAG_HIGHRISK
```

Some indication variables may also be part of the admission-management pathway, so final adjustment decisions require clinical and causal review.

## Possible Effect Modifiers

Important effect modifiers include:

```text
spontaneous labor vs non-spontaneous labor
parity
gestational age group
induction indication
epidural timing or use
delivery mode subgroup
```

The spontaneous versus non-spontaneous labor subgroup is especially important because COVID policies may affect these care pathways differently.
