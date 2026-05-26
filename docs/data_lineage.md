# Data Lineage

## Raw To Interim Flow

The raw workbook is stored at `data/raw/rawdata_all.xlsx`. The rule-based framework reads only the analysis sheet `用這一個` and writes a derived interim dataset to:

```text
data/interim/delivery_mode_interim_v01.xlsx
```

The raw workbook is never modified. All original variables are preserved in the interim dataset. Rule-based outputs are appended as new flag variables and derived clean variables.

## Variable Transformation

The current interim dataset adds:

```text
FLAG_STAGE1_EXTREME
FLAG_STAGE2_NEGATIVE
FLAG_STAGE2_EXTREME
FLAG_DUPLICATE_CHART
FLAG_DELIVERY_TIME_CONFLICT
FLAG_GESTAT_INCONSISTENT
GESTAT_WEEKS_DECIMAL
STAGE2_MINS_CLEAN
```

`GESTAT_WEEKS_DECIMAL` is derived from `GESTAT_WEEK + GESTAT_DAY / 7`.

`STAGE2_MINS_CLEAN` preserves valid original values and converts only `STAGE2_MINS == -1` to missing in the derived variable. The original `STAGE2_MINS` remains unchanged.

## Flag Logic

`FLAG_STAGE1_EXTREME` is set to 1 when `STAGE1_MINS > 1440`.

`FLAG_STAGE2_NEGATIVE` is set to 1 when `STAGE2_MINS < 0`.

`FLAG_STAGE2_EXTREME` is set to 1 when `STAGE2_MINS > 240`.

`FLAG_DUPLICATE_CHART` is set to 1 for all rows where `CHART` is duplicated.

`FLAG_DELIVERY_TIME_CONFLICT` is set to 1 when `DELIVERY_TIME` and `DELIVERY_TIME.1` differ, treating two missing values as non-conflicting.

`FLAG_GESTAT_INCONSISTENT` is set to 1 when `GESTAT_DAYS-ALL` differs from `GESTAT_WEEK + GESTAT_DAY / 7` by more than 0.01.

## Reproducibility Notes

Run the scripts from the project root:

```bash
python scripts/01_data_audit.py
python scripts/02_variable_definition_exploration.py
python scripts/03_rule_based_cleaning_framework.py
```

Generated reports are written to `outputs/`. Interim datasets are written to `data/interim/`. These files are reproducible from the scripts and are intentionally excluded from Git because they may contain sensitive clinical data.

## Git Workflow

Commit source code, documentation, and environment files. Do not commit raw clinical data, interim datasets, processed datasets, or generated reports.

Recommended workflow:

```bash
git status
git add .
git commit -m "Describe reproducible workflow change"
git push
```
