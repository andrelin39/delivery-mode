from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_processed_candidate_v01.xlsx"
POLICY_CALENDAR_FILE = PROJECT_ROOT / "docs" / "policy_calendar_template.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

ANALYSIS_VARIABLE_FILE = PROCESSED_DIR / "delivery_mode_analysis_variables_v01.xlsx"


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def read_processed() -> pd.DataFrame:
    if not PROCESSED_FILE.exists():
        raise FileNotFoundError(
            f"Processed candidate not found: {PROCESSED_FILE}. Run scripts/04_analysis_cohort_framework.py first."
        )
    return pd.read_excel(PROCESSED_FILE, sheet_name="processed_candidate_v01")


def read_policy_calendar() -> pd.DataFrame:
    if not POLICY_CALENDAR_FILE.exists():
        raise FileNotFoundError(f"Policy calendar template not found: {POLICY_CALENDAR_FILE}")
    return pd.read_csv(POLICY_CALENDAR_FILE, encoding="utf-8", keep_default_na=False)


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    try:
        writer = pd.ExcelWriter(path, engine="xlsxwriter")
    except ModuleNotFoundError:
        writer = pd.ExcelWriter(path, engine="openpyxl")
    with writer:
        for sheet_name, data in sheets.items():
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def normalize_missing_text(series: pd.Series) -> pd.Series:
    return series.astype("string").fillna("").str.strip()


def contains_labor_symptom(pgadm: pd.Series) -> pd.Series:
    text = normalize_missing_text(pgadm)
    return text.str.contains("陣痛|破水|現血", regex=True, na=False)


def has_induction_reason(reason: pd.Series) -> pd.Series:
    text = normalize_missing_text(reason)
    return text.ne("") & text.ne("NA") & text.ne("<MISSING>")


def create_delivery_date_final(df: pd.DataFrame) -> pd.Series:
    primary = pd.to_datetime(df["DELIVERY_TIME"], errors="coerce")
    secondary = pd.to_datetime(df["DELIVERY_TIME.1"], errors="coerce")
    return primary.fillna(secondary)


def create_labor_onset_group(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    labor_symptom = contains_labor_symptom(df["PGADM"])
    induction_reason = has_induction_reason(df["Reason of induction"])

    group = pd.Series("uncertain", index=df.index, dtype="string")
    source = pd.Series("no_candidate_rule_matched", index=df.index, dtype="string")

    group.loc[labor_symptom] = "spontaneous_labor"
    source.loc[labor_symptom] = "PGADM contains labor symptom: 陣痛/破水/現血"

    non_spontaneous = induction_reason & ~labor_symptom
    group.loc[non_spontaneous] = "non_spontaneous_or_induction"
    source.loc[non_spontaneous] = "Reason of induction non-missing and PGADM lacks labor symptoms"

    uncertain = group.eq("uncertain")
    return group, source, uncertain.astype("int64")


def delivery_mode_mapping(df: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    raw = normalize_missing_text(df["DELIVER_MODE"])
    mapping = {
        "NSD": "NSD",
        "VED": "VED",
        "C/S": "CS",
        "CS": "CS",
    }
    mapped = raw.map(mapping).fillna("other_or_uncertain").astype("string")

    report = (
        pd.DataFrame({"DELIVER_MODE": raw.replace("", "<MISSING>"), "DELIVERY_MODE_GROUP": mapped})
        .value_counts(["DELIVER_MODE", "DELIVERY_MODE_GROUP"])
        .reset_index(name="count")
        .sort_values(["DELIVERY_MODE_GROUP", "DELIVER_MODE"])
    )
    report["pct"] = report["count"] / len(df) if len(df) else np.nan
    return mapped, report


def parse_policy_dates(calendar: pd.DataFrame) -> pd.DataFrame:
    parsed = calendar.copy()
    for col in ["start_date", "end_date"]:
        parsed[f"{col}_parsed"] = pd.to_datetime(
            parsed[col].replace({"": pd.NA, "NA": pd.NA, "NaN": pd.NA, "nan": pd.NA}),
            errors="coerce",
        )
    parsed["has_usable_date_range"] = parsed["start_date_parsed"].notna() & parsed["end_date_parsed"].notna()
    return parsed


def assign_policy_period(delivery_date: pd.Series, calendar: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    parsed = parse_policy_dates(calendar)
    usable = parsed[parsed["has_usable_date_range"]].copy()
    period = pd.Series(pd.NA, index=delivery_date.index, dtype="string")

    for _, row in usable.iterrows():
        mask = delivery_date.notna() & delivery_date.between(row["start_date_parsed"], row["end_date_parsed"], inclusive="both")
        period.loc[mask] = row["period_name"]

    status_records: list[dict[str, Any]] = []
    status_records.append(
        {
            "status_item": "policy_calendar_has_usable_date_ranges",
            "status_value": "yes" if len(usable) > 0 else "no",
            "numeric_value": int(len(usable)),
            "details": f"{len(usable)} of {len(parsed)} rows have usable start_date and end_date.",
        }
    )
    status_records.append(
        {
            "status_item": "covid_policy_period_assigned_count",
            "status_value": "assigned" if period.notna().sum() > 0 else "none_assigned",
            "numeric_value": int(period.notna().sum()),
            "details": "If zero, fill docs/policy_calendar_template.csv with confirmed external policy dates.",
        }
    )
    status_records.append(
        {
            "status_item": "calendar_warning",
            "status_value": "active" if len(usable) == 0 else "inactive",
            "numeric_value": np.nan,
            "details": "Policy calendar dates are placeholders; COVID_POLICY_PERIOD remains missing."
            if len(usable) == 0
            else "Policy period assignment used date ranges from the calendar file.",
        }
    )

    return period, pd.DataFrame(status_records)


def policy_calendar_report(calendar: pd.DataFrame, status: pd.DataFrame) -> dict[str, pd.DataFrame]:
    parsed = parse_policy_dates(calendar)
    return {
        "calendar_status": status,
        "policy_calendar": parsed,
    }


def labor_onset_distribution(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    group_counts = (
        df["LABOR_ONSET_GROUP"]
        .astype("string")
        .fillna("<MISSING>")
        .value_counts(dropna=False)
        .rename_axis("LABOR_ONSET_GROUP")
        .reset_index(name="count")
    )
    group_counts["pct"] = group_counts["count"] / len(df) if len(df) else np.nan

    source_counts = (
        df["LABOR_ONSET_RULE_SOURCE"]
        .astype("string")
        .fillna("<MISSING>")
        .value_counts(dropna=False)
        .rename_axis("LABOR_ONSET_RULE_SOURCE")
        .reset_index(name="count")
    )
    source_counts["pct"] = source_counts["count"] / len(df) if len(df) else np.nan

    pgadm_cross = (
        df.groupby(["PGADM", "LABOR_ONSET_GROUP"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["LABOR_ONSET_GROUP", "count"], ascending=[True, False])
    )

    return {
        "group_distribution": group_counts,
        "rule_source_distribution": source_counts,
        "pgadm_by_group": pgadm_cross,
    }


def analysis_variable_summary(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    variables = [
        "DELIVERY_DATE_FINAL",
        "LABOR_ONSET_GROUP",
        "LABOR_ONSET_RULE_SOURCE",
        "FLAG_LABOR_ONSET_UNCERTAIN",
        "DELIVERY_MODE_GROUP",
        "COVID_POLICY_PERIOD",
    ]
    rows = []
    for var in variables:
        rows.append(
            {
                "variable": var,
                "dtype": str(df[var].dtype),
                "missing_count": int(df[var].isna().sum()),
                "missing_pct": df[var].isna().mean(),
                "unique_count": int(df[var].nunique(dropna=True)),
            }
        )
    summary = pd.DataFrame(rows)

    period_counts = (
        df["COVID_POLICY_PERIOD"]
        .astype("string")
        .fillna("<MISSING>")
        .value_counts(dropna=False)
        .rename_axis("COVID_POLICY_PERIOD")
        .reset_index(name="count")
    )
    period_counts["pct"] = period_counts["count"] / len(df) if len(df) else np.nan

    return {
        "analysis_variable_summary": summary,
        "covid_policy_period_counts": period_counts,
    }


def build_analysis_variables(df: pd.DataFrame, calendar: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    analysis = df.copy()
    analysis["DELIVERY_DATE_FINAL"] = create_delivery_date_final(analysis)
    labor_group, labor_source, labor_uncertain = create_labor_onset_group(analysis)
    analysis["LABOR_ONSET_GROUP"] = labor_group
    analysis["LABOR_ONSET_RULE_SOURCE"] = labor_source
    analysis["FLAG_LABOR_ONSET_UNCERTAIN"] = labor_uncertain
    analysis["DELIVERY_MODE_GROUP"], mapping_report = delivery_mode_mapping(analysis)
    analysis["COVID_POLICY_PERIOD"], policy_status = assign_policy_period(analysis["DELIVERY_DATE_FINAL"], calendar)
    return analysis, mapping_report, policy_status


def main() -> None:
    ensure_dirs()
    processed = read_processed()
    calendar = read_policy_calendar()
    analysis, mapping_report, policy_status = build_analysis_variables(processed, calendar)

    write_excel(ANALYSIS_VARIABLE_FILE, {"analysis_variables_v01": analysis})
    write_excel(OUTPUT_DIR / "21_policy_calendar_status.xlsx", policy_calendar_report(calendar, policy_status))
    write_excel(OUTPUT_DIR / "22_labor_onset_group_distribution.xlsx", labor_onset_distribution(analysis))
    write_excel(OUTPUT_DIR / "23_delivery_mode_mapping_report.xlsx", {"mapping_report": mapping_report})
    write_excel(OUTPUT_DIR / "24_analysis_variable_summary.xlsx", analysis_variable_summary(analysis))

    print("Policy calendar and analysis variable engineering completed.")
    print(f"Rows preserved: {len(analysis)}")
    print(f"Analysis variable dataset: {ANALYSIS_VARIABLE_FILE}")
    print(f"Usable policy calendar rows: {parse_policy_dates(calendar)['has_usable_date_range'].sum()}")


if __name__ == "__main__":
    main()
