# Preliminary Analysis Plan

## Descriptive Analysis

Describe the delivery population by COVID policy period once institutional policy dates are confirmed. Report maternal age, parity, gestational age, BMI, delivery mode, labor duration, epidural-related variables, and neonatal outcomes.

Use monthly delivery counts to show whether the data window supports the proposed policy periods. Calendar periods should not be interpreted as policy exposure unless linked to documented hospital policy changes.

## Subgroup Analysis

Pre-specify subgroup analyses for:

```text
spontaneous labor
non-spontaneous labor or induction
mixed or uncertain onset
nulliparous versus multiparous
delivery mode groups
epidural timing groups
```

Mixed onset cases should be retained and described rather than silently excluded.

## COVID-Period Comparison

Compare outcomes across policy periods such as pre-COVID, early COVID policy period, and coexistence era only after confirming exact policy dates. If the available dataset starts after the pre-COVID period, the primary comparison may need to focus on policy-intensity periods within the observed COVID era.

## Spontaneous Vs Non-Spontaneous Subgroup Analysis

Operationalize labor onset using candidate rules from `PGADM` and `Reason of induction`. The conservative initial approach is:

1. Possible spontaneous labor: `PGADM` contains `陣痛`, `破水`, or `現血` and does not contain `引產`.
2. Possible non-spontaneous labor: `PGADM` contains `引產`, or induction reason is present.
3. Uncertain or mixed onset: values containing both spontaneous symptoms and induction terms.

This classification should be validated with clinicians before final modeling.

## Delivery Mode Modeling

Treat `DELIVER_MODE` as the primary outcome. Candidate approaches include multinomial logistic regression for `NSD`, `VED`, and `C/S`, or binary logistic regression if a clinically justified contrast is selected.

The main exposure should be COVID policy period. Models should estimate the association between policy period and delivery mode, overall and stratified by labor onset group.

## Possible Regression Strategy

Initial model sequence:

1. Unadjusted model: delivery mode as outcome and policy period as exposure.
2. Demographic-adjusted model: add age and baseline sociodemographic covariates.
3. Obstetric-adjusted model: add parity, gravidity, gestational age, BMI, and indication/risk variables after causal review.
4. Stratified model: repeat within spontaneous and non-spontaneous labor groups.

Avoid adjusting for variables that may be mediators, such as epidural timing or labor duration, in the primary total-effect model. Use mediation-oriented models only as secondary analyses.

## Sensitivity Analysis Ideas

Potential sensitivity analyses:

```text
exclude or flag records with delivery time conflicts
exclude or separately analyze duplicate CHART records
compare results with and without STAGE1_MINS extreme cases
compare results with and without STAGE2_MINS extreme cases
treat mixed labor onset as spontaneous, non-spontaneous, or separate subgroup
use alternative COVID policy period cut points
model C/S versus non-C/S as a binary outcome
model VED versus NSD among vaginal deliveries
```

All sensitivity analyses should preserve original records and be implemented with reproducible flags.
