from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "rawdata_all.xlsx"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
TARGET_SHEET = "用這一個"

INTERIM_FILE = INTERIM_DIR / "delivery_mode_interim_v01.xlsx"
RULES_LOG_FILE = OUTPUT_DIR / "12_cleaning_rules_log.xlsx"
SUMMARY_FILE = OUTPUT_DIR / "13_cleaning_summary.xlsx"


def ensure_dirs() -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_raw_data() -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Raw file not found: {RAW_FILE}")
    return pd.read_excel(RAW_FILE, sheet_name=TARGET_SHEET, engine="openpyxl")


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    try:
        writer = pd.ExcelWriter(path, engine="xlsxwriter")
    except ModuleNotFoundError:
        writer = pd.ExcelWriter(path, engine="openpyxl")

    with writer:
        for sheet_name, data in sheets.items():
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def numeric(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def bool_to_flag(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype("int64")


def build_interim_dataset(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()

    stage1 = numeric(df, "STAGE1_MINS")
    stage2 = numeric(df, "STAGE2_MINS")
    gestat_week = numeric(df, "GESTAT_WEEK")
    gestat_day = numeric(df, "GESTAT_DAY")
    gestat_observed = numeric(df, "GESTAT_DAYS-ALL")
    gestat_decimal = gestat_week + gestat_day / 7

    delivery_left = df["DELIVERY_TIME"]
    delivery_right = df["DELIVERY_TIME.1"]
    delivery_conflict = ~(delivery_left.eq(delivery_right) | (delivery_left.isna() & delivery_right.isna()))

    df["FLAG_STAGE1_EXTREME"] = bool_to_flag(stage1 > 1440)
    df["FLAG_STAGE2_NEGATIVE"] = bool_to_flag(stage2 < 0)
    df["FLAG_STAGE2_EXTREME"] = bool_to_flag(stage2 > 240)
    df["FLAG_DUPLICATE_CHART"] = bool_to_flag(df["CHART"].duplicated(keep=False))
    df["FLAG_DELIVERY_TIME_CONFLICT"] = bool_to_flag(delivery_conflict)
    df["FLAG_GESTAT_INCONSISTENT"] = bool_to_flag((gestat_observed - gestat_decimal).abs() > 0.01)

    df["GESTAT_WEEKS_DECIMAL"] = gestat_decimal
    df["STAGE2_MINS_CLEAN"] = stage2.mask(stage2 == -1, np.nan)

    return df


def cleaning_rules_log(interim_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = [
        {
            "variable": "STAGE1_MINS",
            "rule_type": "flag",
            "original_value": "> 1440",
            "cleaned_value": "raw value preserved",
            "flag_triggered": "FLAG_STAGE1_EXTREME",
            "rationale": "First stage duration above 24 hours may be clinically possible but requires review before exclusion or transformation.",
        },
        {
            "variable": "STAGE2_MINS",
            "rule_type": "flag",
            "original_value": "< 0",
            "cleaned_value": "raw value preserved",
            "flag_triggered": "FLAG_STAGE2_NEGATIVE",
            "rationale": "Negative labor duration is not physically interpretable and may represent a missing or database code.",
        },
        {
            "variable": "STAGE2_MINS",
            "rule_type": "flag",
            "original_value": "> 240",
            "cleaned_value": "raw value preserved",
            "flag_triggered": "FLAG_STAGE2_EXTREME",
            "rationale": "Second stage duration above 240 minutes is an extreme value requiring clinical review.",
        },
        {
            "variable": "CHART",
            "rule_type": "flag",
            "original_value": "duplicated non-missing CHART",
            "cleaned_value": "raw value preserved",
            "flag_triggered": "FLAG_DUPLICATE_CHART",
            "rationale": "Duplicated chart numbers may indicate multiple admissions, multiple deliveries, or duplicate records.",
        },
        {
            "variable": "DELIVERY_TIME / DELIVERY_TIME.1",
            "rule_type": "flag",
            "original_value": "DELIVERY_TIME != DELIVERY_TIME.1",
            "cleaned_value": "raw values preserved",
            "flag_triggered": "FLAG_DELIVERY_TIME_CONFLICT",
            "rationale": "Duplicated source header has conflicting timestamp values in at least one row; source field definition must be confirmed.",
        },
        {
            "variable": "GESTAT_DAYS-ALL",
            "rule_type": "flag",
            "original_value": "abs(GESTAT_DAYS-ALL - (GESTAT_WEEK + GESTAT_DAY / 7)) > 0.01",
            "cleaned_value": "raw value preserved",
            "flag_triggered": "FLAG_GESTAT_INCONSISTENT",
            "rationale": "Exploration suggests GESTAT_DAYS-ALL is decimal gestational weeks; inconsistent records require review.",
        },
        {
            "variable": "GESTAT_WEEK / GESTAT_DAY",
            "rule_type": "derived_clean_variable",
            "original_value": "GESTAT_WEEK, GESTAT_DAY",
            "cleaned_value": "GESTAT_WEEKS_DECIMAL = GESTAT_WEEK + GESTAT_DAY / 7",
            "flag_triggered": "none",
            "rationale": "Creates an explicit decimal gestational weeks variable without overwriting original fields.",
        },
        {
            "variable": "STAGE2_MINS",
            "rule_type": "derived_clean_variable",
            "original_value": "-1",
            "cleaned_value": "NaN in STAGE2_MINS_CLEAN",
            "flag_triggered": "FLAG_STAGE2_NEGATIVE",
            "rationale": "The only negative value observed is -1, treated as a suspected missing code in the derived variable only.",
        },
    ]
    return pd.DataFrame(records)


def flag_summary(interim_df: pd.DataFrame) -> pd.DataFrame:
    flag_columns = [column for column in interim_df.columns if column.startswith("FLAG_")]
    records = []
    row_count = len(interim_df)
    for column in flag_columns:
        count = int(interim_df[column].sum())
        records.append(
            {
                "flag": column,
                "count": count,
                "affected_pct": count / row_count if row_count else np.nan,
            }
        )
    return pd.DataFrame(records)


def cleaned_variable_summary(interim_df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for column in ["GESTAT_WEEKS_DECIMAL", "STAGE2_MINS_CLEAN"]:
        series = pd.to_numeric(interim_df[column], errors="coerce")
        records.append(
            {
                "cleaned_variable": column,
                "non_missing_count": int(series.notna().sum()),
                "missing_count": int(series.isna().sum()),
                "min": series.min(),
                "max": series.max(),
                "mean": series.mean(),
                "median": series.median(),
            }
        )
    return pd.DataFrame(records)


def missingness_changes(interim_df: pd.DataFrame) -> pd.DataFrame:
    pairs = [
        ("STAGE2_MINS", "STAGE2_MINS_CLEAN"),
        ("GESTAT_DAYS-ALL", "GESTAT_WEEKS_DECIMAL"),
    ]
    records = []
    row_count = len(interim_df)
    for raw_col, clean_col in pairs:
        raw_series = pd.to_numeric(interim_df[raw_col], errors="coerce")
        clean_series = pd.to_numeric(interim_df[clean_col], errors="coerce")
        raw_missing = int(raw_series.isna().sum())
        clean_missing = int(clean_series.isna().sum())
        both_missing = raw_series.isna() & clean_series.isna()
        both_present_close = raw_series.notna() & clean_series.notna() & np.isclose(
            raw_series, clean_series, atol=0.000001
        )
        unchanged = both_missing | both_present_close
        changed_count = int((~unchanged).sum())
        records.append(
            {
                "raw_variable": raw_col,
                "cleaned_variable": clean_col,
                "raw_missing_count": raw_missing,
                "cleaned_missing_count": clean_missing,
                "missing_count_change": clean_missing - raw_missing,
                "value_changed_count": changed_count,
                "affected_pct": changed_count / row_count if row_count else np.nan,
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    ensure_dirs()
    raw_df = read_raw_data()
    interim_df = build_interim_dataset(raw_df)

    write_excel(INTERIM_FILE, {"interim_v01": interim_df})
    write_excel(RULES_LOG_FILE, {"cleaning_rules_log": cleaning_rules_log(interim_df)})
    write_excel(
        SUMMARY_FILE,
        {
            "flag_counts": flag_summary(interim_df),
            "cleaned_variable_stats": cleaned_variable_summary(interim_df),
            "missingness_changes": missingness_changes(interim_df),
        },
    )

    print("Rule-based cleaning framework completed.")
    print(f"Rows: {len(interim_df)}")
    print(f"Original columns: {len(raw_df.columns)}")
    print(f"Interim columns: {len(interim_df.columns)}")
    print(f"Interim dataset: {INTERIM_FILE}")
    print(f"Rules log: {RULES_LOG_FILE}")
    print(f"Summary: {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
