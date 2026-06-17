# Midwifery Table 1 Refactor Notes

## Rationale

The existing analysis table includes baseline variables, outcome variables, data-quality flags, and variables used for model validation. For the Midwifery manuscript, Table 1 was refactored into a publication-ready baseline characteristics table focused on describing women according to admission pathway during the strict COVID-19 admission management period.

The refactored table does not modify the analytic dataset and does not overwrite any existing publication table.

## Variables Removed

The following variables were removed from the Midwifery Table 1 version:

- Delivery mode
- Cesarean delivery indicator
- Operative delivery indicator
- Apgar scores
- Stage 1 labor duration
- Stage 2 labor duration
- Review and data-quality flag variables

## Variables Retained

The retained baseline characteristics are:

- Maternal age, years
- Body mass index, kg/m²
- Gravidity
- Parity
- Marriage status
- Education level
- Gestational age at delivery, weeks
- Birth weight, g

## Manuscript Terminology

The Midwifery manuscript table uses the following admission pathway terminology:

- Symptomatic admission
- Planned induction admission

These labels are used in place of the analysis-variable coding labels to improve readability and align the table with manuscript language.

## Bug Fix — 2026-06-17

### Root Cause

The original script used `LABOR_ONSET_GROUP_FINAL` for group assignment. This column applies a strict classification rule that reclassifies 16 ambiguous records (`FLAG_LABOR_ONSET_REQUIRES_REVIEW == 1`) from `spontaneous_labor` to `non_spontaneous_or_induction`. In a prior version of the dataset, `LABOR_ONSET_GROUP_FINAL` was `NaN` for these 16 records, causing the `isin(GROUP_ORDER)` filter in `make_table_dataset` to exclude them from the analytic cohort. The result was that the categorical variables (Marriage status, Education level) summed to 1348 rather than 1364.

### Fix

Group assignment now uses `LABOR_ONSET_GROUP` (the base/main-analysis classification) instead of `LABOR_ONSET_GROUP_FINAL` (the strict/sensitivity-analysis classification). All 16 flagged records are correctly classified as `spontaneous_labor` under the base rule and are retained in the cohort.

This aligns Table 1 with the pre-specified final analytic cohort:

| Group | N |
|---|---|
| Symptomatic admission | 697 |
| Planned induction admission | 667 |
| **Total** | **1364** |

### Validation Step Added

A `validate_cohort()` function was added to `scripts/13_midwifery_table1_refactor.py`. It raises `ValueError` if:

1. `FLAG_LABOR_ONSET_REQUIRES_REVIEW == 1` records are absent from the cohort (indicating an unintentional sensitivity exclusion).
2. The sum of group-level non-missing counts for any categorical variable does not equal the total non-missing count (indicating implicit record exclusion).

The validation is printed to stdout on every run with per-variable OK/FAIL status.
