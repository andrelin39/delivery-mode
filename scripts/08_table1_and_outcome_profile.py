from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v02.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

GROUP_COL = "LABOR_ONSET_GROUP"

CONTINUOUS_VARS = [
    "Age",
    "BMI",
    "GESTAT_WEEKS_DECIMAL",
    "BIRTH_WEIGHT",
    "BIRTH_LENGTH",
    "STAGE1_MINS",
    "STAGE2_MINS_CLEAN",
    "A_S_1",
    "A_S_5",
]

CATEGORICAL_VARS = [
    "DELIVERY_MODE_GROUP",
    "PGADM",
    "Reason of induction",
    "EDUCATION",
    "MARRIAGE",
    "FLAG_STAGE1_EXTREME",
    "FLAG_STAGE2_EXTREME",
    "FLAG_LABOR_ONSET_REQUIRES_REVIEW",
]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_analysis_data() -> pd.DataFrame:
    if not ANALYSIS_FILE.exists():
        raise FileNotFoundError(
            f"Analysis v02 dataset not found: {ANALYSIS_FILE}. Run scripts/07_labor_onset_validation.py first."
        )
    return pd.read_excel(ANALYSIS_FILE, sheet_name="analysis_variables_v02")


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    try:
        writer = pd.ExcelWriter(path, engine="xlsxwriter")
    except ModuleNotFoundError:
        writer = pd.ExcelWriter(path, engine="openpyxl")
    with writer:
        for sheet_name, data in sheets.items():
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def numeric_series(df: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(df[column], errors="coerce")


def iqr_text(series: pd.Series) -> str:
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    if pd.isna(q1) or pd.isna(q3):
        return ""
    return f"{q1:.2f}, {q3:.2f}"


def continuous_table(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = ["Overall", *df[GROUP_COL].dropna().astype(str).sort_values().unique().tolist()]
    for variable in CONTINUOUS_VARS:
        for group in groups:
            subset = df if group == "Overall" else df[df[GROUP_COL].astype(str).eq(group)]
            series = numeric_series(subset, variable)
            non_missing = series.dropna()
            rows.append(
                {
                    "variable": variable,
                    "group": group,
                    "n": int(non_missing.count()),
                    "mean": non_missing.mean(),
                    "SD": non_missing.std(),
                    "median": non_missing.median(),
                    "IQR": iqr_text(non_missing),
                    "min": non_missing.min(),
                    "max": non_missing.max(),
                    "missing_n": int(series.isna().sum()),
                    "missing_pct": series.isna().mean() if len(series) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def categorical_table(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = ["Overall", *df[GROUP_COL].dropna().astype(str).sort_values().unique().tolist()]
    for variable in CATEGORICAL_VARS:
        for group in groups:
            subset = df if group == "Overall" else df[df[GROUP_COL].astype(str).eq(group)]
            series = subset[variable].astype("string").fillna("<MISSING>")
            denominator = len(subset)
            counts = series.value_counts(dropna=False)
            for value, count in counts.items():
                rows.append(
                    {
                        "variable": variable,
                        "group": group,
                        "category": value,
                        "count": int(count),
                        "column_pct": count / denominator if denominator else np.nan,
                        "group_n": denominator,
                    }
                )
    return pd.DataFrame(rows)


def delivery_mode_profile(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    overall = (
        df["DELIVERY_MODE_GROUP"]
        .astype("string")
        .fillna("<MISSING>")
        .value_counts(dropna=False)
        .rename_axis("DELIVERY_MODE_GROUP")
        .reset_index(name="count")
    )
    overall["pct"] = overall["count"] / len(df) if len(df) else np.nan

    by_group = (
        df.groupby([GROUP_COL, "DELIVERY_MODE_GROUP"], dropna=False)
        .size()
        .reset_index(name="count")
    )
    totals = df.groupby(GROUP_COL, dropna=False).size().reset_index(name="group_n")
    by_group = by_group.merge(totals, on=GROUP_COL, how="left")
    by_group["within_group_pct"] = by_group["count"] / by_group["group_n"]

    rate_rows = []
    for outcome in ["CS", "VED", "NSD"]:
        for group, subset in df.groupby(GROUP_COL, dropna=False):
            count = int(subset["DELIVERY_MODE_GROUP"].eq(outcome).sum())
            rate_rows.append(
                {
                    "outcome": outcome,
                    GROUP_COL: group,
                    "count": count,
                    "group_n": len(subset),
                    "rate": count / len(subset) if len(subset) else np.nan,
                }
            )
    return {
        "overall_distribution": overall,
        "by_labor_onset": by_group,
        "mode_rates_by_labor_onset": pd.DataFrame(rate_rows),
    }


def summarize_by_group(df: pd.DataFrame, variables: list[str], group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = df.groupby(group_cols, dropna=False)
    for group_values, subset in grouped:
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        group_data = dict(zip(group_cols, group_values))
        for variable in variables:
            series = numeric_series(subset, variable)
            non_missing = series.dropna()
            row = {
                **group_data,
                "variable": variable,
                "n": int(non_missing.count()),
                "mean": non_missing.mean(),
                "SD": non_missing.std(),
                "median": non_missing.median(),
                "IQR": iqr_text(non_missing),
                "min": non_missing.min(),
                "max": non_missing.max(),
                "missing_n": int(series.isna().sum()),
                "missing_pct": series.isna().mean() if len(series) else np.nan,
                "group_n": len(subset),
            }
            rows.append(row)
    return pd.DataFrame(rows)


def neonatal_outcome_profile(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    profiled = df.copy()
    profiled["LOW_APGAR_1_CANDIDATE"] = (numeric_series(profiled, "A_S_1") < 7).astype("int64")
    profiled["LOW_APGAR_5_CANDIDATE"] = (numeric_series(profiled, "A_S_5") < 7).astype("int64")
    continuous = summarize_by_group(profiled, ["BIRTH_WEIGHT", "A_S_1", "A_S_5"], [GROUP_COL])

    rate_rows = []
    for variable in ["LOW_APGAR_1_CANDIDATE", "LOW_APGAR_5_CANDIDATE"]:
        for group, subset in profiled.groupby(GROUP_COL, dropna=False):
            count = int(subset[variable].sum())
            rate_rows.append(
                {
                    GROUP_COL: group,
                    "candidate_outcome": variable,
                    "count": count,
                    "group_n": len(subset),
                    "rate": count / len(subset) if len(subset) else np.nan,
                }
            )
    return {"continuous_neonatal": continuous, "low_apgar_candidates": pd.DataFrame(rate_rows)}


def labor_duration_profile(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    duration = summarize_by_group(
        df,
        ["STAGE1_MINS", "STAGE2_MINS_CLEAN"],
        [GROUP_COL, "DELIVERY_MODE_GROUP"],
    )
    flag_rows = []
    for flag_col in ["FLAG_STAGE1_EXTREME", "FLAG_STAGE2_EXTREME"]:
        for group_values, subset in df.groupby([GROUP_COL, "DELIVERY_MODE_GROUP"], dropna=False):
            onset, mode = group_values
            count = int(pd.to_numeric(subset[flag_col], errors="coerce").fillna(0).sum())
            flag_rows.append(
                {
                    GROUP_COL: onset,
                    "DELIVERY_MODE_GROUP": mode,
                    "flag": flag_col,
                    "count": count,
                    "group_n": len(subset),
                    "rate": count / len(subset) if len(subset) else np.nan,
                }
            )
    return {"duration_summary": duration, "extreme_flag_rates": pd.DataFrame(flag_rows)}


def save_delivery_mode_figure(df: pd.DataFrame) -> None:
    ctab = pd.crosstab(df[GROUP_COL], df["DELIVERY_MODE_GROUP"], normalize="index")
    ctab = ctab[[col for col in ["NSD", "VED", "CS", "other_or_uncertain"] if col in ctab.columns]]
    ax = ctab.plot(kind="bar", stacked=True, figsize=(8, 5))
    ax.set_ylabel("Within-group proportion")
    ax.set_xlabel("Labor onset group")
    ax.set_title("Delivery Mode By Labor Onset Group")
    ax.legend(title="Delivery mode", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "fig_delivery_mode_by_labor_onset.png", dpi=150)
    plt.close()


def save_boxplot(df: pd.DataFrame, variable: str, filename: str, title: str) -> None:
    plot_df = df[[GROUP_COL, variable]].copy()
    plot_df[variable] = pd.to_numeric(plot_df[variable], errors="coerce")
    groups = plot_df[GROUP_COL].dropna().astype(str).sort_values().unique().tolist()
    data = [plot_df.loc[plot_df[GROUP_COL].astype(str).eq(group), variable].dropna() for group in groups]
    plt.figure(figsize=(8, 5))
    plt.boxplot(data, tick_labels=groups, showfliers=False)
    plt.ylabel(variable)
    plt.xlabel("Labor onset group")
    plt.title(title)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / filename, dpi=150)
    plt.close()


def create_figures(df: pd.DataFrame) -> None:
    save_delivery_mode_figure(df)
    save_boxplot(df, "STAGE1_MINS", "fig_stage1_distribution_by_labor_onset.png", "Stage 1 Duration By Labor Onset Group")
    save_boxplot(df, "STAGE2_MINS_CLEAN", "fig_stage2_distribution_by_labor_onset.png", "Stage 2 Duration By Labor Onset Group")
    save_boxplot(df, "BIRTH_WEIGHT", "fig_birth_weight_by_labor_onset.png", "Birth Weight By Labor Onset Group")


def key_findings(df: pd.DataFrame) -> dict[str, Any]:
    onset_counts = df[GROUP_COL].value_counts().to_dict()
    cs_rates = (
        df.assign(IS_CS=df["DELIVERY_MODE_GROUP"].eq("CS").astype("int64"))
        .groupby(GROUP_COL)["IS_CS"]
        .mean()
        .to_dict()
    )
    ved_rates = (
        df.assign(IS_VED=df["DELIVERY_MODE_GROUP"].eq("VED").astype("int64"))
        .groupby(GROUP_COL)["IS_VED"]
        .mean()
        .to_dict()
    )
    stage1_medians = df.groupby(GROUP_COL)["STAGE1_MINS"].median().to_dict()
    birth_weight_means = df.groupby(GROUP_COL)["BIRTH_WEIGHT"].mean().to_dict()
    return {
        "onset_counts": onset_counts,
        "cs_rates": cs_rates,
        "ved_rates": ved_rates,
        "stage1_medians": stage1_medians,
        "birth_weight_means": birth_weight_means,
    }


def main() -> None:
    ensure_dirs()
    df = read_analysis_data()

    write_excel(
        OUTPUT_DIR / "29_table1_by_labor_onset.xlsx",
        {
            "continuous": continuous_table(df),
            "categorical": categorical_table(df),
        },
    )
    write_excel(OUTPUT_DIR / "30_delivery_mode_outcome_profile.xlsx", delivery_mode_profile(df))
    write_excel(OUTPUT_DIR / "31_neonatal_outcome_profile.xlsx", neonatal_outcome_profile(df))
    write_excel(OUTPUT_DIR / "32_labor_duration_profile.xlsx", labor_duration_profile(df))
    create_figures(df)

    findings = key_findings(df)
    print("Table 1 and preliminary outcome profiling completed.")
    print(f"Rows assessed: {len(df)}")
    print(f"Labor onset counts: {findings['onset_counts']}")
    print(f"C/S rates: {findings['cs_rates']}")
    print(f"VED rates: {findings['ved_rates']}")


if __name__ == "__main__":
    main()
