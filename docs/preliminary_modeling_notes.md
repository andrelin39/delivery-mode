# Preliminary Delivery Mode Modeling Notes

## Current Modeling Purpose

The current models are a skeleton for delivery mode outcome modeling before COVID policy periods are available. They test whether the pipeline can construct crude and adjusted models for delivery mode outcomes and describe the association between labor onset group and delivery mode.

These models are preliminary. They should be used for workflow testing, model diagnostics, and planning.

## Delivery Mode Is The Outcome

`DELIVERY_MODE_GROUP` is treated as the delivery outcome. Binary outcomes are derived as:

```text
CS_BINARY = 1 for CS, 0 for NSD or VED
OPERATIVE_DELIVERY_BINARY = 1 for CS or VED, 0 for NSD
```

The three-category outcome is:

```text
DELIVERY_MODE_GROUP = NSD, VED, CS
```

## Labor Onset Is Not Policy Exposure

`LABOR_ONSET_GROUP` is a key clinical pathway variable. It may stratify or modify how policy affects delivery outcomes, but it is not the COVID policy exposure.

The eventual main exposure should be `COVID_POLICY_PERIOD`, assigned from externally confirmed hospital policy calendar dates.

## Crude Versus Adjusted Interpretation

The crude model estimates the unadjusted association between labor onset group and delivery mode outcomes.

The adjusted model includes:

```text
Age
BMI
GESTAT_WEEKS_DECIMAL
BIRTH_WEIGHT
GRAVIDA
PARA
```

These adjusted estimates remain associational. They are not causal effects.

## Not A COVID Policy Effect

These models cannot be interpreted as COVID policy effects because `COVID_POLICY_PERIOD` is not yet assigned. Differences by labor onset group may reflect clinical indication, admission pathway, parity, gestational age, fetal size, provider decision-making, or documentation patterns.

## Future Model With COVID_POLICY_PERIOD

After completing the policy calendar, the planned model should use COVID policy period as the main exposure and delivery mode as the outcome.

Candidate formula:

```text
CS_BINARY ~ COVID_POLICY_PERIOD
          + LABOR_ONSET_GROUP
          + COVID_POLICY_PERIOD:LABOR_ONSET_GROUP
          + Age
          + BMI
          + GESTAT_WEEKS_DECIMAL
          + BIRTH_WEIGHT
          + GRAVIDA
          + PARA
```

For multinomial delivery mode:

```text
DELIVERY_MODE_GROUP ~ COVID_POLICY_PERIOD
                    + LABOR_ONSET_GROUP
                    + COVID_POLICY_PERIOD:LABOR_ONSET_GROUP
                    + Age
                    + BMI
                    + GESTAT_WEEKS_DECIMAL
                    + BIRTH_WEIGHT
                    + GRAVIDA
                    + PARA
```

Labor duration and epidural variables may be mediators and should not be included in the primary total-effect model without a causal analysis plan.
