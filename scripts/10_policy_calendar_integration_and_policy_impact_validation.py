from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_V02_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v02.xlsx"
ANALYSIS_V03_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v03.xlsx"
POLICY_CALENDAR_FILE = PROJECT_ROOT / "docs" / "policy_calendar_template.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

POLICY_PERIOD_ORDER = [
    "pre_policy_period",
    "strict_covid_policy_period",
    "policy_relaxation_period",
]
LABOR_ONSET_ORDER = ["spontaneous_labor", "non_spontaneous_or_induction"]
DELIVERY_MODE_ORDER = ["NSD", "VED", "VBAC", "CS"]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_V03_FILE.parent.mkdir(parents=True, exist_ok=True)


def read_analysis_v02() -> pd.DataFrame:
    if not ANALYSIS_V02_FILE.exists():
        raise FileNotFoundError(f"Analysis v02 dataset not found: {ANALYSIS_V02_FILE}")
    return pd.read_excel(ANALYSIS_V02_FILE, sheet_name="analysis_variables_v02")


def read_policy_calendar() -> pd.DataFrame:
    if not POLICY_CALENDAR_FILE.exists():
        raise FileNotFoundError(f"Policy calendar not found: {POLICY_CALENDAR_FILE}")
    return pd.read_csv(POLICY_CALENDAR_FILE, encoding="utf-8", keep_default_na=False)


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    try:
        writer = pd.ExcelWriter(path, engine="xlsxwriter")
    except ModuleNotFoundError:
        writer = pd.ExcelWriter(path, engine="openpyxl")
    with writer:
        for sheet_name, data in sheets.items():
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def normalize_text(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip()


def contains_any(series: pd.Series, terms: list[str]) -> pd.Series:
    result = pd.Series(False, index=series.index)
    text = normalize_text(series)
    for term in terms:
        result = result | text.str.contains(term, regex=False, na=False)
    return result


def create_delivery_date_final(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["DELIVERY_TIME"], errors="coerce")


def create_labor_onset_final(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    pgadm = normalize_text(df["PGADM"])
    pgadm_numeric = pd.to_numeric(pgadm, errors="coerce")
    has_induction = (pgadm_numeric.eq(0) | contains_any(pgadm, ["引產"])).fillna(False)
    has_labor_sign = (pgadm_numeric.eq(1) | contains_any(pgadm, ["陣痛", "破水", "現血"])).fillna(False)

    group = pd.Series(pd.NA, index=df.index, dtype="string")
    group.loc[has_induction] = "non_spontaneous_or_induction"
    group.loc[has_labor_sign & ~has_induction] = "spontaneous_labor"

    mixed = has_induction & has_labor_sign
    group.loc[mixed] = "non_spontaneous_or_induction"

    lineage = pd.Series("PGADM final clinical definition", index=df.index, dtype="string")
    lineage.loc[has_induction & ~has_labor_sign] = "PGADM=0 or PGADM contains 引產"
    lineage.loc[has_labor_sign & ~has_induction] = "PGADM=1 or PGADM contains 陣痛/破水/現血"
    lineage.loc[mixed] = "PGADM contains both induction and labor-sign terms; classified as non_spontaneous_or_induction and flagged for review"
    lineage.loc[group.isna()] = "No final PGADM rule matched"

    return group, mixed.astype("int64"), lineage


def create_delivery_mode_final(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    raw = normalize_text(df["DELIVER_MODE"]).str.upper()
    numeric = pd.to_numeric(raw, errors="coerce")

    group = pd.Series(pd.NA, index=df.index, dtype="string")
    group.loc[numeric.eq(0) | raw.eq("C/S") | raw.eq("CS")] = "CS"
    group.loc[numeric.eq(1) | raw.eq("NSD")] = "NSD"
    group.loc[numeric.eq(2) | raw.eq("VED")] = "VED"
    group.loc[numeric.eq(3) | raw.eq("VBAC")] = "VBAC"

    lineage = pd.Series("DELIVER_MODE final codebook mapping", index=df.index, dtype="string")
    lineage.loc[group.eq("CS")] = "DELIVER_MODE=0 or C/S"
    lineage.loc[group.eq("NSD")] = "DELIVER_MODE=1 or NSD"
    lineage.loc[group.eq("VED")] = "DELIVER_MODE=2 or VED"
    lineage.loc[group.eq("VBAC")] = "DELIVER_MODE=3 or VBAC"
    lineage.loc[group.isna()] = "No final DELIVER_MODE codebook rule matched"
    return group, lineage


def assign_policy_period(delivery_date: pd.Series, calendar: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    parsed = calendar.copy()
    parsed["start_date_parsed"] = pd.to_datetime(parsed["start_date"], errors="coerce")
    parsed["end_date_parsed"] = pd.to_datetime(parsed["end_date"], errors="coerce")

    period = pd.Series(pd.NA, index=delivery_date.index, dtype="string")
    lineage = pd.Series("No policy calendar period matched DELIVERY_TIME", index=delivery_date.index, dtype="string")
    for _, row in parsed.iterrows():
        start = row["start_date_parsed"]
        end = row["end_date_parsed"]
        if pd.isna(start) or pd.isna(end):
            continue
        mask = delivery_date.notna() & delivery_date.between(start, end, inclusive="both")
        period.loc[mask] = row["period_name"]
        lineage.loc[mask] = f"DELIVERY_TIME linked to {row['period_name']} ({row['start_date']} to {row['end_date']})"
    return period, lineage


def build_v03_dataset(df: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["DELIVERY_DATE_FINAL"] = create_delivery_date_final(result)
    result["DELIVERY_DATE_FINAL_LINEAGE"] = "Derived from DELIVERY_TIME only; DELIVERY_TIME.1 retained but not used for analysis linkage"

    labor_group, labor_review, labor_lineage = create_labor_onset_final(result)
    result["LABOR_ONSET_GROUP_FINAL"] = labor_group
    result["FLAG_LABOR_ONSET_REQUIRES_REVIEW"] = labor_review
    result["LABOR_ONSET_GROUP_FINAL_LINEAGE"] = labor_lineage

    delivery_group, delivery_lineage = create_delivery_mode_final(result)
    result["DELIVERY_MODE_GROUP_FINAL"] = delivery_group
    result["DELIVERY_MODE_GROUP_FINAL_LINEAGE"] = delivery_lineage

    result["CS_BINARY_FINAL"] = delivery_group.eq("CS").astype("Int64")
    result.loc[delivery_group.isna(), "CS_BINARY_FINAL"] = pd.NA
    result["CS_BINARY_FINAL_LINEAGE"] = "Derived from DELIVERY_MODE_GROUP_FINAL: CS=1; NSD/VED/VBAC=0"

    result["OPERATIVE_DELIVERY_BINARY_FINAL"] = delivery_group.isin(["CS", "VED"]).astype("Int64")
    result.loc[delivery_group.isna(), "OPERATIVE_DELIVERY_BINARY_FINAL"] = pd.NA
    result["OPERATIVE_DELIVERY_BINARY_FINAL_LINEAGE"] = "Derived from DELIVERY_MODE_GROUP_FINAL: CS/VED=1; NSD/VBAC=0"

    result["VAGINAL_BIRTH_BINARY_FINAL"] = delivery_group.isin(["NSD", "VED", "VBAC"]).astype("Int64")
    result.loc[delivery_group.isna(), "VAGINAL_BIRTH_BINARY_FINAL"] = pd.NA
    result["VAGINAL_BIRTH_BINARY_FINAL_LINEAGE"] = "Derived from DELIVERY_MODE_GROUP_FINAL: NSD/VED/VBAC=1; CS=0"

    stage2 = pd.to_numeric(result["STAGE2_MINS"], errors="coerce")
    result["STAGE2_MINS_CLEAN_FINAL"] = stage2.mask(stage2 < 0)
    result["STAGE2_MINS_CLEAN_FINAL_LINEAGE"] = "Derived from STAGE2_MINS; values <0 set to missing"

    policy_period, policy_lineage = assign_policy_period(result["DELIVERY_DATE_FINAL"], calendar)
    result["COVID_POLICY_PERIOD_FINAL"] = pd.Categorical(policy_period, categories=POLICY_PERIOD_ORDER, ordered=True)
    result["COVID_POLICY_PERIOD_FINAL_LINEAGE"] = policy_lineage
    return result


def count_pct(series: pd.Series, categories: list[str] | None = None) -> pd.DataFrame:
    values = series.astype("string")
    if categories is None:
        counts = values.fillna("<MISSING>").value_counts(dropna=False).rename_axis(series.name).reset_index(name="count")
    else:
        counts = values.value_counts(dropna=False).reindex(categories, fill_value=0).rename_axis(series.name).reset_index(name="count")
    counts["pct"] = counts["count"] / len(series) if len(series) else np.nan
    return counts


def crosstab_long(df: pd.DataFrame, row: str, col: str, row_order: list[str] | None = None, col_order: list[str] | None = None) -> pd.DataFrame:
    row_values = df[row].astype("string")
    col_values = df[col].astype("string")
    counts = pd.crosstab(row_values, col_values, dropna=False)
    if row_order is not None:
        counts = counts.reindex(row_order, fill_value=0)
    if col_order is not None:
        counts = counts.reindex(columns=col_order, fill_value=0)
    denom = counts.sum(axis=1).replace(0, np.nan)
    long = counts.reset_index().melt(id_vars=row, var_name=col, value_name="count")
    long = long.merge(denom.rename("row_n").reset_index(), on=row, how="left")
    long["row_pct"] = long["count"] / long["row_n"]
    return long


def rate_by_group(df: pd.DataFrame, group_cols: list[str], outcome_col: str, rate_name: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_values, subset in df.groupby(group_cols, dropna=False, observed=False):
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        outcome = pd.to_numeric(subset[outcome_col], errors="coerce")
        valid = outcome.dropna()
        rows.append(
            {
                **dict(zip(group_cols, group_values)),
                "n": int(valid.count()),
                "event_count": int(valid.sum()) if len(valid) else 0,
                rate_name: valid.mean() if len(valid) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def monthly_delivery_count(df: pd.DataFrame) -> pd.DataFrame:
    month = df["DELIVERY_DATE_FINAL"].dt.to_period("M").astype("string")
    out = month.value_counts().sort_index().rename_axis("delivery_month").reset_index(name="delivery_count")
    return out


def policy_period_distribution_report(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "period_distribution": count_pct(df["COVID_POLICY_PERIOD_FINAL"], POLICY_PERIOD_ORDER),
        "monthly_delivery_count": monthly_delivery_count(df),
    }


def pgadm_by_policy_report(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    pgadm = crosstab_long(df, "COVID_POLICY_PERIOD_FINAL", "PGADM", POLICY_PERIOD_ORDER)
    labor = crosstab_long(df, "COVID_POLICY_PERIOD_FINAL", "LABOR_ONSET_GROUP_FINAL", POLICY_PERIOD_ORDER, LABOR_ONSET_ORDER)
    induction_rate = rate_by_group(
        df.assign(NON_SPONTANEOUS_FINAL=df["LABOR_ONSET_GROUP_FINAL"].eq("non_spontaneous_or_induction").astype("Int64")),
        ["COVID_POLICY_PERIOD_FINAL"],
        "NON_SPONTANEOUS_FINAL",
        "non_spontaneous_or_induction_rate",
    )
    return {"pgadm_by_policy": pgadm, "labor_onset_by_policy": labor, "induction_rate_by_policy": induction_rate}


def delivery_mode_by_policy_report(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    mode = crosstab_long(df, "COVID_POLICY_PERIOD_FINAL", "DELIVERY_MODE_GROUP_FINAL", POLICY_PERIOD_ORDER, DELIVERY_MODE_ORDER)
    rates = []
    for mode_name, rate_name in [("CS", "cs_rate"), ("VED", "ved_rate"), ("NSD", "nsd_rate")]:
        tmp = rate_by_group(
            df.assign(_OUTCOME=df["DELIVERY_MODE_GROUP_FINAL"].eq(mode_name).astype("Int64")),
            ["COVID_POLICY_PERIOD_FINAL"],
            "_OUTCOME",
            rate_name,
        )
        rates.append(tmp)
    combined = rates[0]
    for tmp in rates[1:]:
        combined = combined.merge(tmp[["COVID_POLICY_PERIOD_FINAL", tmp.columns[-1]]], on="COVID_POLICY_PERIOD_FINAL", how="outer")
    vbac = (
        df["DELIVERY_MODE_GROUP_FINAL"]
        .eq("VBAC")
        .groupby(df["COVID_POLICY_PERIOD_FINAL"], observed=False)
        .sum()
        .reindex(POLICY_PERIOD_ORDER, fill_value=0)
        .rename("vbac_count")
        .reset_index()
    )
    combined = combined.merge(vbac, on="COVID_POLICY_PERIOD_FINAL", how="outer")
    return {"delivery_mode_by_policy": mode, "mode_rates_by_policy": combined}


def policy_labor_delivery_report(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    cross = (
        df.groupby(["COVID_POLICY_PERIOD_FINAL", "LABOR_ONSET_GROUP_FINAL", "DELIVERY_MODE_GROUP_FINAL"], dropna=False, observed=False)
        .size()
        .reset_index(name="count")
    )
    totals = (
        df.groupby(["COVID_POLICY_PERIOD_FINAL", "LABOR_ONSET_GROUP_FINAL"], dropna=False, observed=False)
        .size()
        .reset_index(name="stratum_n")
    )
    cross = cross.merge(totals, on=["COVID_POLICY_PERIOD_FINAL", "LABOR_ONSET_GROUP_FINAL"], how="left")
    cross["stratum_pct"] = cross["count"] / cross["stratum_n"].replace(0, np.nan)
    cs_rate = rate_by_group(df, ["COVID_POLICY_PERIOD_FINAL", "LABOR_ONSET_GROUP_FINAL"], "CS_BINARY_FINAL", "cs_rate")
    return {"policy_labor_delivery_mode": cross, "cs_rate_by_policy_labor": cs_rate}


def validation_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for period in POLICY_PERIOD_ORDER:
        subset = df[df["COVID_POLICY_PERIOD_FINAL"].astype("string").eq(period)]
        n = len(subset)
        spontaneous = subset[subset["LABOR_ONSET_GROUP_FINAL"].astype("string").eq("spontaneous_labor")]
        non_spontaneous = subset[subset["LABOR_ONSET_GROUP_FINAL"].astype("string").eq("non_spontaneous_or_induction")]
        rows.append(
            {
                "policy_period": period,
                "n": n,
                "induction_non_spontaneous_rate": non_spontaneous.shape[0] / n if n else np.nan,
                "cs_rate": subset["CS_BINARY_FINAL"].mean() if n else np.nan,
                "cs_rate_among_spontaneous_labor": spontaneous["CS_BINARY_FINAL"].mean() if len(spontaneous) else np.nan,
                "cs_rate_among_non_spontaneous_induction": non_spontaneous["CS_BINARY_FINAL"].mean() if len(non_spontaneous) else np.nan,
                "ved_rate": subset["DELIVERY_MODE_GROUP_FINAL"].eq("VED").mean() if n else np.nan,
                "nsd_rate": subset["DELIVERY_MODE_GROUP_FINAL"].eq("NSD").mean() if n else np.nan,
            }
        )
    return pd.DataFrame(rows)


def variable_lineage_summary(df: pd.DataFrame) -> pd.DataFrame:
    lineage_cols = [col for col in df.columns if col.endswith("_LINEAGE")]
    rows = []
    for col in lineage_cols:
        value_counts = df[col].astype("string").fillna("<MISSING>").value_counts(dropna=False)
        for value, count in value_counts.items():
            rows.append({"lineage_variable": col, "lineage_value": value, "count": int(count)})
    return pd.DataFrame(rows)


def save_bar(path: Path, data: pd.DataFrame, x: str, y: str, title: str, ylabel: str) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.bar(data[x].astype(str), data[y])
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def create_figures(df: pd.DataFrame) -> None:
    monthly = monthly_delivery_count(df)
    save_bar(OUTPUT_DIR / "fig_monthly_delivery_count.png", monthly, "delivery_month", "delivery_count", "Monthly Delivery Count", "Count")

    summary = validation_summary(df)
    save_bar(
        OUTPUT_DIR / "fig_induction_rate_by_policy_period.png",
        summary,
        "policy_period",
        "induction_non_spontaneous_rate",
        "Induction / Non-Spontaneous Rate by Policy Period",
        "Rate",
    )
    save_bar(OUTPUT_DIR / "fig_cs_rate_by_policy_period.png", summary, "policy_period", "cs_rate", "CS Rate by Policy Period", "Rate")

    cs_stratified = rate_by_group(df, ["COVID_POLICY_PERIOD_FINAL", "LABOR_ONSET_GROUP_FINAL"], "CS_BINARY_FINAL", "cs_rate")
    pivot = cs_stratified.pivot(index="COVID_POLICY_PERIOD_FINAL", columns="LABOR_ONSET_GROUP_FINAL", values="cs_rate").reindex(POLICY_PERIOD_ORDER)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    x = np.arange(len(pivot.index))
    width = 0.36
    for i, labor_group in enumerate(LABOR_ONSET_ORDER):
        values = pivot[labor_group] if labor_group in pivot.columns else pd.Series(np.nan, index=pivot.index)
        ax.bar(x + (i - 0.5) * width, values, width, label=labor_group)
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index.astype(str), rotation=30, ha="right")
    ax.set_ylabel("Rate")
    ax.set_title("CS Rate by Policy Period and Labor Onset")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "fig_cs_rate_by_policy_and_labor_onset.png", dpi=200)
    plt.close(fig)


def write_reports(df: pd.DataFrame, calendar: pd.DataFrame) -> None:
    write_excel(
        OUTPUT_DIR / "38_policy_period_distribution.xlsx",
        {**policy_period_distribution_report(df), "policy_calendar": calendar},
    )
    write_excel(OUTPUT_DIR / "39_pgadm_by_policy_period.xlsx", pgadm_by_policy_report(df))
    write_excel(OUTPUT_DIR / "40_delivery_mode_by_policy_period.xlsx", delivery_mode_by_policy_report(df))
    write_excel(OUTPUT_DIR / "41_policy_period_by_labor_onset_delivery_mode.xlsx", policy_labor_delivery_report(df))
    write_excel(
        OUTPUT_DIR / "42_policy_impact_validation_summary.xlsx",
        {
            "validation_summary": validation_summary(df),
            "variable_lineage_summary": variable_lineage_summary(df),
        },
    )


def main() -> None:
    ensure_dirs()
    calendar = read_policy_calendar()
    df_v02 = read_analysis_v02()
    df_v03 = build_v03_dataset(df_v02, calendar)
    write_excel(
        ANALYSIS_V03_FILE,
        {
            "analysis_variables_v03": df_v03,
            "policy_calendar": calendar,
            "variable_lineage_summary": variable_lineage_summary(df_v03),
        },
    )
    write_reports(df_v03, calendar)
    create_figures(df_v03)

    summary = validation_summary(df_v03)
    print("Created v03 dataset and policy impact validation outputs.")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
