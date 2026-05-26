# Preliminary Descriptive Findings

## Sample Characteristics

This descriptive profiling uses `data/processed/delivery_mode_analysis_variables_v02.xlsx`. Records are grouped by `LABOR_ONSET_GROUP`.

The outputs are descriptive only. They should be used to understand sample structure, data quality, and outcome distributions before policy-period analysis.

## Labor Onset Groups

The current operational groups are:

```text
spontaneous_labor
non_spontaneous_or_induction
```

Table 1 is written to `outputs/29_table1_by_labor_onset.xlsx` and summarizes maternal characteristics, obstetric characteristics, neonatal measures, labor duration variables, delivery mode, admission presentation, and validation flags.

## Delivery Mode Profile

Delivery mode is treated as an outcome. The delivery mode outcome profile is written to:

```text
outputs/30_delivery_mode_outcome_profile.xlsx
outputs/fig_delivery_mode_by_labor_onset.png
```

This report describes the distribution of `DELIVERY_MODE_GROUP` overall and within labor onset groups. It does not estimate policy effects.

## Neonatal Outcome Profile

The neonatal profile includes:

```text
BIRTH_WEIGHT
A_S_1
A_S_5
LOW_APGAR_1_CANDIDATE = A_S_1 < 7
LOW_APGAR_5_CANDIDATE = A_S_5 < 7
```

Outputs are written to `outputs/31_neonatal_outcome_profile.xlsx` and `outputs/fig_birth_weight_by_labor_onset.png`.

## Labor Duration Profile

The labor duration profile includes:

```text
STAGE1_MINS
STAGE2_MINS_CLEAN
FLAG_STAGE1_EXTREME
FLAG_STAGE2_EXTREME
```

Results are stratified by both `LABOR_ONSET_GROUP` and `DELIVERY_MODE_GROUP`. Outputs are written to `outputs/32_labor_duration_profile.xlsx`, `outputs/fig_stage1_distribution_by_labor_onset.png`, and `outputs/fig_stage2_distribution_by_labor_onset.png`.

## Not A COVID Policy Effect

These findings must not be interpreted as COVID policy effects. The current policy calendar still contains placeholder dates, so `COVID_POLICY_PERIOD` is not yet assigned.

Any differences between labor onset groups may reflect clinical indication, admission pathway, parity, gestational age, provider decision-making, or data coding, not hospital COVID policy.

## Next Step

The next analytic step requires a completed external policy calendar with confirmed hospital policy start and end dates. After that, analyses can compare delivery outcomes across COVID policy periods and evaluate whether patterns differ by labor onset group.
