from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "rawdata_all.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
TARGET_SHEET = "用這一個"


def ensure_output_dir() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_target_sheet() -> pd.DataFrame:
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


def numeric_summary(series: pd.Series) -> pd.DataFrame:
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).to_frame("value").reset_index(names="statistic")


def save_histogram(series: pd.Series, path: Path, title: str, xlabel: str, bins: int = 40) -> None:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    plt.figure(figsize=(9, 5))
    plt.hist(numeric, bins=bins, edgecolor="black")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def delivery_time_comparison(df: pd.DataFrame) -> None:
    columns = [column for column in df.columns if str(column).startswith("DELIVERY_TIME")]
    if len(columns) < 2:
        summary = pd.DataFrame(
            [{"status": "less_than_two_delivery_time_columns", "columns_found": "; ".join(columns)}]
        )
        write_excel(OUTPUT_DIR / "06_delivery_time_comparison.xlsx", {"summary": summary})
        return

    left, right = columns[:2]
    left_series = df[left]
    right_series = df[right]
    equality = left_series.eq(right_series) | (left_series.isna() & right_series.isna())
    both_missing = left_series.isna() & right_series.isna()
    missing_diff = left_series.isna() != right_series.isna()

    summary = pd.DataFrame(
        [
            {
                "column_1": left,
                "column_2": right,
                "dtype_1": str(left_series.dtype),
                "dtype_2": str(right_series.dtype),
                "same_dtype": str(left_series.dtype) == str(right_series.dtype),
                "all_values_identical": bool(equality.all()),
                "different_value_count": int((~equality).sum()),
                "missing_count_1": int(left_series.isna().sum()),
                "missing_count_2": int(right_series.isna().sum()),
                "missing_count_identical": int(left_series.isna().sum()) == int(right_series.isna().sum()),
                "rows_with_missing_difference": int(missing_diff.sum()),
                "rows_both_missing": int(both_missing.sum()),
            }
        ]
    )

    first_20 = pd.DataFrame(
        {
            "row_number": np.arange(1, min(len(df), 20) + 1),
            left: left_series.head(20),
            right: right_series.head(20),
            "identical": equality.head(20).to_numpy(),
        }
    )
    differences = df.loc[~equality, [left, right]].copy()
    differences.insert(0, "row_number", differences.index + 2)

    write_excel(
        OUTPUT_DIR / "06_delivery_time_comparison.xlsx",
        {"summary": summary, "first_20": first_20, "differences": differences.head(200)},
    )


def decimal_places(value: Any) -> int | None:
    if pd.isna(value):
        return None
    text = f"{float(value):.12f}".rstrip("0").rstrip(".")
    if "." not in text:
        return 0
    return len(text.split(".", 1)[1])


def gestation_definition_check(df: pd.DataFrame) -> None:
    cols = ["GESTAT_WEEK", "GESTAT_DAY", "GESTAT_DAYS-ALL"]
    data = df[cols].copy()
    week = pd.to_numeric(data["GESTAT_WEEK"], errors="coerce")
    day = pd.to_numeric(data["GESTAT_DAY"], errors="coerce")
    observed = pd.to_numeric(data["GESTAT_DAYS-ALL"], errors="coerce")
    calculated_total_days = week * 7 + day
    calculated_decimal_weeks = week + day / 7

    compare = data.copy()
    compare["calculated_total_days"] = calculated_total_days
    compare["diff_if_total_days"] = observed - calculated_total_days
    compare["calculated_decimal_weeks"] = calculated_decimal_weeks
    compare["diff_if_decimal_weeks"] = observed - calculated_decimal_weeks
    compare["abs_diff_if_total_days"] = compare["diff_if_total_days"].abs()
    compare["abs_diff_if_decimal_weeks"] = compare["diff_if_decimal_weeks"].abs()

    decimal_distribution = (
        observed.map(decimal_places)
        .value_counts(dropna=False)
        .rename_axis("decimal_places")
        .reset_index(name="count")
        .sort_values("decimal_places", na_position="last")
    )

    hypothesis_summary = pd.DataFrame(
        [
            {
                "hypothesis": "GESTAT_DAYS-ALL = total gestational days",
                "exact_match_count": int((compare["abs_diff_if_total_days"] == 0).sum()),
                "within_0_001_count": int((compare["abs_diff_if_total_days"] <= 0.001).sum()),
                "mean_abs_diff": float(compare["abs_diff_if_total_days"].mean()),
                "max_abs_diff": float(compare["abs_diff_if_total_days"].max()),
            },
            {
                "hypothesis": "GESTAT_DAYS-ALL = decimal gestational weeks",
                "exact_match_count": int((compare["abs_diff_if_decimal_weeks"] == 0).sum()),
                "within_0_001_count": int((compare["abs_diff_if_decimal_weeks"] <= 0.001).sum()),
                "mean_abs_diff": float(compare["abs_diff_if_decimal_weeks"].mean()),
                "max_abs_diff": float(compare["abs_diff_if_decimal_weeks"].max()),
            },
        ]
    )

    min_max = pd.DataFrame(
        [
            {
                "column": "GESTAT_DAYS-ALL",
                "min": observed.min(),
                "max": observed.max(),
                "mean": observed.mean(),
                "median": observed.median(),
            }
        ]
    )

    save_histogram(
        observed,
        OUTPUT_DIR / "07_gestat_days_all_histogram.png",
        "GESTAT_DAYS-ALL Distribution",
        "GESTAT_DAYS-ALL",
    )
    write_excel(
        OUTPUT_DIR / "07_gestation_definition_check.xlsx",
        {
            "first_100": compare.head(100),
            "min_max": min_max,
            "decimal_places": decimal_distribution,
            "hypothesis_summary": hypothesis_summary,
            "comparison_all_rows": compare,
        },
    )


def maybe_hhmm(value: float) -> bool:
    if pd.isna(value) or value < 0:
        return False
    integer_value = int(value)
    minutes = integer_value % 100
    hours = integer_value // 100
    return value == integer_value and 0 <= minutes <= 59 and 0 <= hours <= 99


def stage1_extreme_cases(df: pd.DataFrame) -> None:
    stage1 = pd.to_numeric(df["STAGE1_MINS"], errors="coerce")
    extreme = df.loc[stage1 > 1440].copy()
    extreme.insert(0, "row_number", extreme.index + 2)
    extreme["STAGE1_MINS_mod_5"] = extreme["STAGE1_MINS"] % 5
    extreme["STAGE1_MINS_mod_10"] = extreme["STAGE1_MINS"] % 10
    extreme["STAGE1_MINS_mod_15"] = extreme["STAGE1_MINS"] % 15
    extreme["STAGE1_MINS_mod_30"] = extreme["STAGE1_MINS"] % 30
    extreme["STAGE1_MINS_mod_60"] = extreme["STAGE1_MINS"] % 60
    extreme["possible_hhmm"] = extreme["STAGE1_MINS"].map(maybe_hhmm)

    summary = numeric_summary(extreme["STAGE1_MINS"])
    fixed_multiples = pd.DataFrame(
        [
            {
                "divisor": divisor,
                "all_values_are_multiples": bool(((extreme["STAGE1_MINS"] % divisor) == 0).all()),
                "multiple_count": int(((extreme["STAGE1_MINS"] % divisor) == 0).sum()),
                "total_extreme_count": len(extreme),
            }
            for divisor in [5, 10, 15, 30, 60]
        ]
    )
    hhmm_summary = pd.DataFrame(
        [
            {
                "possible_hhmm_count": int(extreme["possible_hhmm"].sum()),
                "total_extreme_count": len(extreme),
                "possible_hhmm_pct": extreme["possible_hhmm"].mean() if len(extreme) else np.nan,
            }
        ]
    )

    deliver_mode = (
        extreme["DELIVER_MODE"].astype("string").fillna("<MISSING>").value_counts().reset_index()
        if "DELIVER_MODE" in extreme.columns
        else pd.DataFrame()
    )
    deliver_mode.columns = ["DELIVER_MODE", "count"] if not deliver_mode.empty else deliver_mode.columns

    induction_col = "Reason of induction"
    induction = (
        extreme[induction_col].astype("string").fillna("<MISSING>").value_counts().reset_index()
        if induction_col in extreme.columns
        else pd.DataFrame()
    )
    induction.columns = [induction_col, "count"] if not induction.empty else induction.columns

    context_cols = [
        column
        for column in [
            "STAGE1_MINS",
            "STAGE2_MINS",
            "DELIVER_MODE",
            "Reason of induction",
            "PGADM",
            "GESTAT_WEEK",
            "GESTAT_DAY",
            "CERVIX10_TIME",
            "DELIVERY_TIME",
            "DELIVERY_TIME.1",
            "PARTO_NO",
            "BABY_NO",
            "CHART",
            "ACC_NO",
        ]
        if column in extreme.columns
    ]
    first_50 = extreme[["row_number", *context_cols]].head(50)

    save_histogram(
        stage1,
        OUTPUT_DIR / "08_stage1_mins_histogram.png",
        "STAGE1_MINS Distribution",
        "STAGE1_MINS",
    )
    write_excel(
        OUTPUT_DIR / "08_stage1_extreme_cases.xlsx",
        {
            "summary_extreme": summary,
            "first_50_extreme": first_50,
            "fixed_multiple_check": fixed_multiples,
            "hhmm_check": hhmm_summary,
            "by_deliver_mode": deliver_mode,
            "by_induction": induction,
            "all_extreme_cases": extreme,
        },
    )


def stage2_negative_values(df: pd.DataFrame) -> None:
    stage2 = pd.to_numeric(df["STAGE2_MINS"], errors="coerce")
    negative = df.loc[stage2 < 0].copy()
    negative.insert(0, "row_number", negative.index + 2)
    value_counts = stage2[stage2 < 0].value_counts().rename_axis("negative_value").reset_index(name="count")
    missing_code_summary = pd.DataFrame(
        [
            {
                "candidate_missing_code": -1,
                "count": int((stage2 == -1).sum()),
                "all_negative_values_are_minus_one": bool((stage2[stage2 < 0] == -1).all()),
                "recommendation": "Treat as suspected missing code only after clinical/database confirmation.",
            }
        ]
    )
    context_cols = [
        column
        for column in [
            "STAGE1_MINS",
            "STAGE2_MINS",
            "DELIVER_MODE",
            "Reason of induction",
            "CERVIX10_TIME",
            "DELIVERY_TIME",
            "DELIVERY_TIME.1",
            "PARTO_NO",
            "BABY_NO",
            "CHART",
            "ACC_NO",
        ]
        if column in negative.columns
    ]
    write_excel(
        OUTPUT_DIR / "09_stage2_negative_values.xlsx",
        {
            "negative_value_counts": value_counts,
            "missing_code_check": missing_code_summary,
            "negative_rows": negative[["row_number", *context_cols]],
        },
    )


def chart_duplicates(df: pd.DataFrame) -> None:
    duplicated = df[df["CHART"].duplicated(keep=False)].copy()
    duplicated.insert(0, "row_number", duplicated.index + 2)

    compare_cols = [
        column
        for column in [
            "CHART",
            "DELIVERY_TIME",
            "DELIVERY_TIME.1",
            "BABY_NO",
            "PARTO_NO",
            "DELIVER_MODE",
            "ACC_NO",
            "BIRTH_WEIGHT",
            "A_S_1",
            "A_S_5",
        ]
        if column in duplicated.columns
    ]
    detail = duplicated[["row_number", *compare_cols]].sort_values(["CHART", "row_number"])

    grouped_records = []
    for chart, group in duplicated.groupby("CHART", dropna=False):
        unique_delivery_times = group[[c for c in ["DELIVERY_TIME", "DELIVERY_TIME.1"] if c in group.columns]].astype("string").agg("|".join, axis=1).nunique()
        unique_baby = group["BABY_NO"].nunique(dropna=True) if "BABY_NO" in group else np.nan
        unique_parto = group["PARTO_NO"].nunique(dropna=True) if "PARTO_NO" in group else np.nan
        unique_mode = group["DELIVER_MODE"].nunique(dropna=True) if "DELIVER_MODE" in group else np.nan
        unique_acc = group["ACC_NO"].nunique(dropna=True) if "ACC_NO" in group else np.nan

        if unique_parto == 1 and unique_acc == 1 and unique_baby > 1:
            suspected_reason = "possible_multiple_birth"
        elif unique_parto > 1 or unique_acc > 1 or unique_delivery_times > 1:
            suspected_reason = "possible_multiple_admissions_or_deliveries"
        elif len(group.drop_duplicates()) == 1:
            suspected_reason = "possible_exact_duplicate_record"
        else:
            suspected_reason = "requires_manual_review"

        grouped_records.append(
            {
                "CHART": chart,
                "row_count": len(group),
                "unique_delivery_times": unique_delivery_times,
                "unique_BABY_NO": unique_baby,
                "unique_PARTO_NO": unique_parto,
                "unique_DELIVER_MODE": unique_mode,
                "unique_ACC_NO": unique_acc,
                "suspected_reason": suspected_reason,
            }
        )

    summary = pd.DataFrame(grouped_records)
    write_excel(
        OUTPUT_DIR / "10_chart_duplicates.xlsx",
        {"summary_by_chart": summary, "duplicate_rows_detail": detail},
    )


def infer_possible_meaning(column: str) -> str:
    mapping = {
        "Age": "Maternal age.",
        "MARRIAGE": "Maternal marital status category.",
        "EDUCATION": "Maternal education category.",
        "GRAVIDA": "Number of pregnancies.",
        "PARA": "Parity.",
        "GESTAT_WEEK": "Gestational age completed weeks.",
        "GESTAT_DAY": "Additional gestational days beyond completed weeks.",
        "GESTAT_DAYS-ALL": "Likely decimal gestational weeks; definition needs confirmation.",
        "BH": "Maternal body height.",
        "BW": "Maternal body weight.",
        "BMI": "Maternal body mass index.",
        "PGADM": "Admission or pregnancy-related category; definition needs confirmation.",
        "Reason of induction": "Induction reason text/category.",
        "CERVIX10_TIME": "Time cervix reached 10 cm.",
        "DELIVERY_TIME": "Delivery timestamp.",
        "DELIVERY_TIME.1": "Second delivery timestamp column from duplicated source header.",
        "DELIVER_MODE": "Delivery mode category.",
        "BIRTH_WEIGHT": "Neonatal birth weight.",
        "BIRTH_LENGTH": "Neonatal birth length.",
        "A_S_1": "Apgar score at 1 minute.",
        "A_S_5": "Apgar score at 5 minutes.",
        "PARTO_NO": "Delivery or parturition identifier.",
        "BABY_NO": "Baby identifier.",
        "CHART": "Maternal chart number.",
        "ACC_NO": "Encounter/account number.",
        "STAGE1_MINS": "First stage labor duration in minutes.",
        "STAGE2_MINS": "Second stage labor duration in minutes.",
    }
    return mapping.get(column, "Needs review against source database or variable definition sheet.")


def suspected_issues_for_column(df: pd.DataFrame, column: str) -> str:
    issues: list[str] = []
    series = df[column]
    missing_pct = series.isna().mean()
    if missing_pct >= 0.5:
        issues.append("high missingness")
    if column == "DELIVERY_TIME":
        issues.append("duplicated source header also appears as DELIVERY_TIME.1")
    if column == "DELIVERY_TIME.1":
        issues.append("duplicated source header; compare with DELIVERY_TIME before use")
    if column == "GESTAT_DAYS-ALL":
        issues.append("name suggests days but values appear decimal weeks")
    if column == "STAGE1_MINS":
        count = int((pd.to_numeric(series, errors="coerce") > 1440).sum())
        if count:
            issues.append(f"{count} values > 1440")
    if column == "STAGE2_MINS":
        numeric = pd.to_numeric(series, errors="coerce")
        neg_count = int((numeric < 0).sum())
        if neg_count:
            issues.append(f"{neg_count} negative values")
    if column == "CHART" and series.duplicated(keep=False).any():
        issues.append("duplicated chart numbers")
    if column in ["DELIVER_MODE", "PGADM", "EDUCATION", "MARRIAGE"]:
        issues.append("allowed category values require codebook confirmation")
    return "; ".join(issues) if issues else ""


def cleaning_recommendation(column: str, suspected_issues: str) -> str:
    if column in ["DELIVERY_TIME", "DELIVERY_TIME.1", "GESTAT_DAYS-ALL", "STAGE1_MINS", "STAGE2_MINS", "CHART"]:
        return "Do not auto-modify; use exploration report and confirm definition first."
    if column in ["DELIVER_MODE", "PGADM", "EDUCATION", "MARRIAGE"]:
        return "Do not recode until official category codebook is confirmed."
    if "high missingness" in suspected_issues:
        return "Flag missingness; do not impute without analysis plan."
    return "Basic type validation and missingness flagging can be automated after definition confirmation."


def preliminary_codebook(df: pd.DataFrame) -> None:
    records = []
    for column in df.columns:
        series = df[column]
        issues = suspected_issues_for_column(df, column)
        records.append(
            {
                "variable_name": column,
                "dtype": str(series.dtype),
                "missing_pct": series.isna().mean(),
                "unique_count": int(series.nunique(dropna=True)),
                "possible_meaning": infer_possible_meaning(column),
                "suspected_issues": issues,
                "cleaning_recommendation": cleaning_recommendation(column, issues),
            }
        )
    write_excel(OUTPUT_DIR / "11_preliminary_codebook.xlsx", {"preliminary_codebook": pd.DataFrame(records)})


def main() -> None:
    ensure_output_dir()
    df = read_target_sheet()

    delivery_time_comparison(df)
    gestation_definition_check(df)
    stage1_extreme_cases(df)
    stage2_negative_values(df)
    chart_duplicates(df)
    preliminary_codebook(df)

    print("Clinical variable definition exploration completed.")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"Outputs written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
