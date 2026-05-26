from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_processed_candidate_v01.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_processed() -> pd.DataFrame:
    if not PROCESSED_FILE.exists():
        raise FileNotFoundError(
            f"Processed candidate not found: {PROCESSED_FILE}. Run scripts/04_analysis_cohort_framework.py first."
        )
    return pd.read_excel(PROCESSED_FILE, sheet_name="processed_candidate_v01")


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    try:
        writer = pd.ExcelWriter(path, engine="xlsxwriter")
    except ModuleNotFoundError:
        writer = pd.ExcelWriter(path, engine="openpyxl")
    with writer:
        for sheet_name, data in sheets.items():
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def value_counts(df: pd.DataFrame, column: str) -> pd.DataFrame:
    counts = df[column].astype("string").fillna("<MISSING>").value_counts(dropna=False)
    return pd.DataFrame(
        {
            "variable": column,
            "value": counts.index.astype(str),
            "count": counts.to_numpy(),
            "pct": counts.to_numpy() / len(df) if len(df) else np.nan,
        }
    )


def temporal_distribution(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    temporal_cols = [
        col
        for col in df.columns
        if pd.api.types.is_datetime64_any_dtype(df[col])
        or any(keyword in col.upper() for keyword in ["DATE", "TIME"])
    ]
    temporal_cols = [col for col in temporal_cols if not col.startswith("FLAG_")]

    records: list[dict[str, Any]] = []
    for col in temporal_cols:
        parsed = pd.to_datetime(df[col], errors="coerce")
        records.append(
            {
                "temporal_variable": col,
                "non_missing_count": int(parsed.notna().sum()),
                "missing_count": int(parsed.isna().sum()),
                "min": parsed.min(),
                "max": parsed.max(),
                "recommended_time_axis": col == "DELIVERY_TIME",
                "note": "No explicit ADMISSION_DATE field found." if col == "DELIVERY_TIME" else "",
            }
        )

    delivery_dt = pd.to_datetime(df["DELIVERY_TIME"], errors="coerce")
    temporal_df = df.copy()
    temporal_df["DELIVERY_DATE_DERIVED"] = delivery_dt.dt.date
    temporal_df["DELIVERY_YEAR"] = delivery_dt.dt.year
    temporal_df["DELIVERY_MONTH"] = delivery_dt.dt.to_period("M").astype("string")

    year_month = (
        temporal_df.groupby(["DELIVERY_YEAR", "DELIVERY_MONTH"], dropna=False)
        .size()
        .reset_index(name="delivery_count")
        .sort_values(["DELIVERY_YEAR", "DELIVERY_MONTH"])
    )

    monthly_counts = (
        temporal_df["DELIVERY_MONTH"]
        .fillna("<MISSING>")
        .value_counts()
        .rename_axis("delivery_month")
        .reset_index(name="delivery_count")
        .sort_values("delivery_month")
    )

    segmentation = pd.DataFrame(
        [
            {
                "candidate_period": "pre-COVID baseline",
                "candidate_definition": "Deliveries before local hospital COVID policy implementation date.",
                "data_feasibility": "Requires external hospital policy date; current dataset begins at 2021-08-21.",
                "recommended_use": "Use only if confirmed policy date precedes observed data window or external comparison data exist.",
            },
            {
                "candidate_period": "early COVID policy period",
                "candidate_definition": "Initial period after major hospital labor/admission restrictions.",
                "data_feasibility": "Can be operationalized by confirmed institutional policy start/end dates, not inferred from outcomes.",
                "recommended_use": "Primary exposure candidate if exact policy dates are available.",
            },
            {
                "candidate_period": "coexistence era",
                "candidate_definition": "Later period when hospital policy normalized under ongoing COVID coexistence.",
                "data_feasibility": "Possible if hospital can provide date of policy relaxation or coexistence transition.",
                "recommended_use": "Compare with early COVID period; avoid arbitrary calendar split unless justified.",
            },
            {
                "candidate_period": "data-driven calendar periods",
                "candidate_definition": "Observed monthly delivery windows in available data.",
                "data_feasibility": "Feasible from DELIVERY_TIME but does not itself prove policy exposure.",
                "recommended_use": "Descriptive only until linked to policy timeline.",
            },
        ]
    )

    return {
        "temporal_variables": pd.DataFrame(records),
        "year_month_distribution": year_month,
        "monthly_delivery_counts": monthly_counts,
        "covid_segmentation_proposal": segmentation,
    }


def contains_any(series: pd.Series, keywords: list[str]) -> pd.Series:
    text = series.astype("string").fillna("")
    pattern = "|".join(keywords)
    return text.str.contains(pattern, regex=True, na=False)


def labor_onset_candidates(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    pgadm = df["PGADM"].astype("string").fillna("")
    reason = df["Reason of induction"].astype("string").fillna("")

    spontaneous_terms = ["陣痛", "破水", "現血"]
    induction_terms = ["引產", "催生", "誘導", "induction", "Induction"]
    uncertain_terms = ["足月妊娠", "門診內診", "胎動減少", "過期妊娠", "胎兒", "體重", "不適"]

    spontaneous_pgadm = contains_any(pgadm, spontaneous_terms)
    induction_pgadm = contains_any(pgadm, induction_terms)
    induction_reason = reason.notna() & reason.ne("")
    uncertain_reason = contains_any(reason, uncertain_terms)

    candidate = df[
        [
            "PGADM",
            "Reason of induction",
            "DELIVER_MODE",
            "GESTAT_WEEKS_DECIMAL",
            "STAGE1_MINS",
            "STAGE2_MINS",
            "PROC_TPALE4A",
            "DRUG_MTMPS",
            "DRUG_MIOXY",
        ]
    ].copy()
    candidate["POSSIBLE_SPONTANEOUS_LABOR"] = spontaneous_pgadm.astype("int64")
    candidate["POSSIBLE_INDUCTION"] = (induction_pgadm | induction_reason).astype("int64")
    candidate["POSSIBLE_UNCERTAIN_ONSET"] = (
        (spontaneous_pgadm & induction_pgadm) | uncertain_reason | (~spontaneous_pgadm & ~induction_pgadm & ~induction_reason)
    ).astype("int64")

    indicators = pd.DataFrame(
        [
            {
                "indicator_type": "possible spontaneous labor indicator",
                "source_variable": "PGADM",
                "candidate_values_or_pattern": "contains 陣痛, 破水, or 現血",
                "rationale": "These terms suggest labor symptoms before or at admission.",
                "limitation": "May coexist with induction terms and needs clinical interpretation.",
            },
            {
                "indicator_type": "possible induction indicator",
                "source_variable": "PGADM",
                "candidate_values_or_pattern": "contains 引產",
                "rationale": "Directly suggests induction admission.",
                "limitation": "Some records combine 引產 with 陣痛 or 現血.",
            },
            {
                "indicator_type": "possible induction indicator",
                "source_variable": "Reason of induction",
                "candidate_values_or_pattern": "non-missing reason",
                "rationale": "Presence of an induction reason suggests planned or indicated induction.",
                "limitation": "Many values are broad indications such as 足月妊娠 and need codebook confirmation.",
            },
            {
                "indicator_type": "labor management variables",
                "source_variable": "PROC_TPALE4A, DRUG_MTMPS, DRUG_MIOXY, STAGE1_MINS, STAGE2_MINS",
                "candidate_values_or_pattern": "procedure/drug/duration fields",
                "rationale": "May describe management after admission rather than onset status.",
                "limitation": "Should not define spontaneous labor without clinical validation.",
            },
        ]
    )

    classification_counts = pd.DataFrame(
        [
            {
                "candidate_class": "possible spontaneous labor",
                "count": int(candidate["POSSIBLE_SPONTANEOUS_LABOR"].sum()),
                "pct": candidate["POSSIBLE_SPONTANEOUS_LABOR"].mean(),
            },
            {
                "candidate_class": "possible induction/non-spontaneous",
                "count": int(candidate["POSSIBLE_INDUCTION"].sum()),
                "pct": candidate["POSSIBLE_INDUCTION"].mean(),
            },
            {
                "candidate_class": "uncertain or mixed onset",
                "count": int(candidate["POSSIBLE_UNCERTAIN_ONSET"].sum()),
                "pct": candidate["POSSIBLE_UNCERTAIN_ONSET"].mean(),
            },
        ]
    )

    logic = pd.DataFrame(
        [
            {
                "step": 1,
                "recommended_logic": "Classify definite non-spontaneous/induction when PGADM contains 引產 and no spontaneous symptom terms are present.",
                "status": "candidate rule; needs clinical validation",
            },
            {
                "step": 2,
                "recommended_logic": "Classify possible spontaneous labor when PGADM contains 陣痛, 破水, or 現血 and PGADM does not contain 引產.",
                "status": "candidate rule; needs validation against admission workflow",
            },
            {
                "step": 3,
                "recommended_logic": "Treat mixed PGADM values such as 引產,陣痛 as uncertain or separate mixed-onset subgroup.",
                "status": "recommended for sensitivity analysis",
            },
            {
                "step": 4,
                "recommended_logic": "Use Reason of induction as supporting evidence for non-spontaneous labor, not as sole classifier until codebook is confirmed.",
                "status": "conservative recommendation",
            },
        ]
    )

    uncertain_cases = candidate[candidate["POSSIBLE_UNCERTAIN_ONSET"] == 1].head(200)

    return {
        "indicator_candidates": indicators,
        "classification_counts": classification_counts,
        "pgadm_distribution": value_counts(df, "PGADM"),
        "reason_induction_distribution": value_counts(df, "Reason of induction"),
        "uncertain_cases_sample": uncertain_cases,
        "recommended_logic": logic,
    }


def outcome_hierarchy() -> pd.DataFrame:
    rows = [
        ("Primary outcome", "DELIVER_MODE", "Delivery mode", "Categorical outcome; compare C/S, NSD, VED or clinically defined grouping."),
        ("Secondary outcome", "STAGE1_MINS", "Labor duration", "Use with FLAG_STAGE1_EXTREME; do not auto-exclude extreme values."),
        ("Secondary outcome", "STAGE2_MINS_CLEAN", "Labor duration", "Derived clean variable with -1 set to missing; use with flags."),
        ("Secondary outcome", "BIRTH_WEIGHT", "Neonatal outcome", "Continuous neonatal outcome."),
        ("Secondary outcome", "A_S_1", "Neonatal outcome", "Apgar score at 1 minute."),
        ("Secondary outcome", "A_S_5", "Neonatal outcome", "Apgar score at 5 minutes."),
        ("Secondary outcome", "EPA timing", "Epidural usage/timing", "Requires definition validation; potential management outcome or mediator."),
        ("Secondary outcome", "FLAG_STAGE1_EXTREME", "Prolonged labor", "Potential prolonged first-stage indicator."),
        ("Secondary outcome", "FLAG_STAGE2_EXTREME", "Prolonged labor", "Potential prolonged second-stage indicator."),
        ("Exploratory outcome", "FLAG_STAGE1_EXTREME", "Extreme stage duration", "Explore chart review and sensitivity analyses."),
        ("Exploratory outcome", "FLAG_DUPLICATE_CHART", "Duplicate chart cases", "May indicate repeat admissions or record structure."),
        ("Exploratory outcome", "DELIVERY_TIME / DELIVERY_TIME.1", "Timing variables", "Resolve duplicate timestamp field before time-to-event use."),
    ]
    return pd.DataFrame(rows, columns=["outcome_level", "variable", "outcome_domain", "operational_note"])


def variable_role_proposal() -> pd.DataFrame:
    rows = [
        ("COVID policy period", "external policy dates + DELIVERY_TIME", "exposure", "Main exposure should be defined externally from hospital policy timeline."),
        ("Labor onset stratum", "PGADM + Reason of induction", "effect modifier", "Spontaneous vs non-spontaneous labor is a key stratification concept."),
        ("Admission/labor management", "EPA timing, EPA time, PAIN, PROC_TPALE4A, DRUG_MTMPS, DRUG_MIOXY", "mediator", "Policy may affect these management processes."),
        ("Delivery mode", "DELIVER_MODE", "outcome", "Primary outcome, not primary exposure."),
        ("Labor duration", "STAGE1_MINS, STAGE2_MINS_CLEAN", "outcome/mediator", "May be affected by management and associated with delivery mode."),
        ("Neonatal outcomes", "BIRTH_WEIGHT, A_S_1, A_S_5", "outcome", "Secondary outcomes."),
        ("Gestational age", "GESTAT_WEEKS_DECIMAL", "confounder", "Associated with timing/policy period and delivery outcomes."),
        ("Maternal demographics", "Age, BMI, EDUCATION, MARRIAGE", "confounder", "Potential baseline differences across policy periods."),
        ("Obstetric history", "GRAVIDA, PARA", "confounder", "Related to labor onset, management, and delivery mode."),
        ("Indication/risk", "PGADM, Reason of induction, DIAG_2, DIAG_3, DIAG_HIGHRISK", "confounder/stratifier", "May capture indication for induction or clinical risk."),
        ("Record exclusions", "FLAG_MISSING_DELIVERY_MODE, FLAG_MISSING_KEY_OUTCOME", "exclusion variable", "Analysis-specific flags; preserve records."),
        ("Data quality flags", "FLAG_STAGE1_EXTREME, FLAG_STAGE2_EXTREME, FLAG_DELIVERY_TIME_CONFLICT, FLAG_DUPLICATE_CHART", "exclusion variable/sensitivity", "Use for sensitivity or chart review, not automatic deletion."),
    ]
    return pd.DataFrame(rows, columns=["concept", "variables", "proposed_role", "rationale"])


def main() -> None:
    ensure_dirs()
    df = read_processed()
    write_excel(OUTPUT_DIR / "17_temporal_distribution.xlsx", temporal_distribution(df))
    write_excel(OUTPUT_DIR / "18_labor_onset_classification_candidates.xlsx", labor_onset_candidates(df))
    write_excel(OUTPUT_DIR / "19_outcome_hierarchy.xlsx", {"outcome_hierarchy": outcome_hierarchy()})
    write_excel(OUTPUT_DIR / "20_variable_role_proposal.xlsx", {"variable_role_proposal": variable_role_proposal()})
    print("COVID policy research operationalization framework completed.")
    print(f"Rows assessed: {len(df)}")
    print(f"Outputs written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
