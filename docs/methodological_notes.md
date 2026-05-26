# Methodological Notes

## Cohort Construction Logic

The analysis cohort framework starts from `data/interim/delivery_mode_interim_v01.xlsx`, not from the raw workbook. The processed candidate dataset is written to:

```text
data/processed/delivery_mode_processed_candidate_v01.xlsx
```

All records are preserved. No row is deleted during this framework step. Cohort eligibility concerns are represented as binary exclusion flags appended to the dataset.

## Exclusion Philosophy

Exclusions should be implemented as transparent flags before any analysis dataset is subsetted. This supports sensitivity analysis and makes the effect of each exclusion visible.

The framework creates flags for:

```text
FLAG_PRETERM
FLAG_POSTTERM
FLAG_EXTREME_BIRTH_WEIGHT
FLAG_EXTREME_MATERNAL_AGE
FLAG_MISSING_DELIVERY_MODE
FLAG_MISSING_KEY_OUTCOME
```

Recommended exclusions are limited to records that cannot support a specific primary analysis, such as missing delivery mode when delivery mode is the primary exposure. Clinical outliers are flagged first and should not be automatically removed without validation.

## Missing Data Considerations

Missingness should be evaluated by variable role. Missing exposure data, missing outcome data, and missing covariate data have different implications.

Complete-case analysis may be reasonable for a narrowly defined outcome but can create selection bias if missingness is related to clinical status, delivery workflow, or documentation processes. The cohort overview report includes missingness patterns to support later missing-data planning.

## Clinical Validation Issues

Several fields require clinical or source-database validation before they are used for final inclusion or exclusion:

```text
DELIVER_MODE
EPA timing
EPA time
PAIN
PGADM
STAGE1_MINS
STAGE2_MINS
CHART duplicates
DELIVERY_TIME versus DELIVERY_TIME.1
```

`GESTAT_DAYS-ALL` appears to represent decimal gestational weeks based on prior exploration, but the misleading field name should still be documented in the final study codebook.

## Reproducibility Principles

The cohort framework is script-based and deterministic. To recreate the current processed candidate:

```bash
python scripts/01_data_audit.py
python scripts/02_variable_definition_exploration.py
python scripts/03_rule_based_cleaning_framework.py
python scripts/04_analysis_cohort_framework.py
```

Raw data, interim datasets, processed candidates, and generated reports are excluded from Git because they may contain sensitive clinical information. The repository tracks scripts, environment files, and documentation needed to reproduce the outputs locally.
