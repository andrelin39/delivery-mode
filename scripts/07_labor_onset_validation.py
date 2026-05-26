from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_V01_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v01.xlsx"
ANALYSIS_V02_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v02.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

LABOR_SYMPTOM_TERMS = ["陣痛", "破水", "現血"]
OTHER_POSSIBLE_LABOR_TERMS = ["落紅", "子宮收縮", "宮縮", "規則宮縮", "腹痛", "腹部抽筋"]
INDUCTION_TERMS = ["引產", "催生", "誘導"]
MEDICAL_INDICATION_TERMS = [
    "胎動減少",
    "過期",
    "胎兒",
    "體重",
    "頭圍",
    "胎頭",
    "水腫",
    "不適",
    "妊娠高血壓",
    "子癲",
    "糖尿",
]
ELECTIVE_OR_SCHEDULING_TERMS = ["足月妊娠", "門診內診", "門診子宮頸", "內診"]
COVID_RELATED_TERMS = ["COVID", "covid", "疫情", "隔離", "確診", "快篩", "PCR"]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_V02_FILE.parent.mkdir(parents=True, exist_ok=True)


def read_analysis_v01() -> pd.DataFrame:
    if not ANALYSIS_V01_FILE.exists():
        raise FileNotFoundError(
            f"Analysis v01 dataset not found: {ANALYSIS_V01_FILE}. Run scripts/06_policy_calendar_and_analysis_variables.py first."
        )
    return pd.read_excel(ANALYSIS_V01_FILE, sheet_name="analysis_variables_v01")


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


def contains_terms(text: pd.Series, terms: list[str]) -> pd.Series:
    if not terms:
        return pd.Series(False, index=text.index)
    return text.str.contains("|".join(terms), regex=True, na=False)


def non_missing_text(series: pd.Series) -> pd.Series:
    text = normalize_text(series)
    return text.ne("") & text.ne("NA") & text.ne("<MISSING>") & text.ne("nan")


def pgadm_value_audit(df: pd.DataFrame) -> pd.DataFrame:
    text = normalize_text(df["PGADM"]).replace("", "<MISSING>")
    counts = text.value_counts(dropna=False).rename_axis("PGADM_raw_value").reset_index(name="count")
    counts["percentage"] = counts["count"] / len(df) if len(df) else np.nan

    audit = counts.copy()
    value_text = normalize_text(audit["PGADM_raw_value"])
    audit["contains_陣痛"] = value_text.str.contains("陣痛", regex=False, na=False)
    audit["contains_破水"] = value_text.str.contains("破水", regex=False, na=False)
    audit["contains_現血"] = value_text.str.contains("現血", regex=False, na=False)
    audit["contains_other_possible_labor_keyword"] = contains_terms(value_text, OTHER_POSSIBLE_LABOR_TERMS)
    audit["contains_induction_keyword"] = contains_terms(value_text, INDUCTION_TERMS)
    has_labor_symptom = audit[["contains_陣痛", "contains_破水", "contains_現血", "contains_other_possible_labor_keyword"]].any(axis=1)

    audit["preliminary_classification_suggestion"] = np.select(
        [
            has_labor_symptom & ~audit["contains_induction_keyword"],
            audit["contains_induction_keyword"] & ~has_labor_symptom,
            has_labor_symptom & audit["contains_induction_keyword"],
        ],
        [
            "likely_spontaneous_labor",
            "likely_induction_or_non_spontaneous",
            "mixed_labor_symptom_and_induction",
        ],
        default="unclear_from_pgadm",
    )
    audit["requires_manual_confirmation"] = np.where(
        audit["preliminary_classification_suggestion"].isin(
            ["mixed_labor_symptom_and_induction", "unclear_from_pgadm"]
        ),
        "yes",
        "no",
    )
    return audit


def reason_of_induction_audit(df: pd.DataFrame) -> pd.DataFrame:
    text = normalize_text(df["Reason of induction"]).replace("", "<MISSING>")
    counts = text.value_counts(dropna=False).rename_axis("reason_of_induction_raw_value").reset_index(name="count")
    counts["percentage"] = counts["count"] / len(df) if len(df) else np.nan

    audit = counts.copy()
    value_text = normalize_text(audit["reason_of_induction_raw_value"])
    audit["is_medical_indication"] = contains_terms(value_text, MEDICAL_INDICATION_TERMS)
    audit["is_elective_or_scheduling_related"] = contains_terms(value_text, ELECTIVE_OR_SCHEDULING_TERMS)
    audit["possibly_covid_policy_related"] = contains_terms(value_text, COVID_RELATED_TERMS)
    audit["requires_manual_confirmation"] = np.where(
        audit["reason_of_induction_raw_value"].eq("<MISSING>"),
        "no",
        np.where(
            audit["is_medical_indication"]
            | audit["is_elective_or_scheduling_related"]
            | audit["possibly_covid_policy_related"],
            "yes",
            "yes",
        ),
    )
    return audit


def create_sensitivity_classification(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    pgadm = normalize_text(result["PGADM"])
    reason = result["Reason of induction"]

    has_labor = contains_terms(pgadm, LABOR_SYMPTOM_TERMS)
    has_reason = non_missing_text(reason)

    sensitivity = pd.Series("uncertain", index=result.index, dtype="string")
    note = pd.Series("No strict labor symptom and no induction reason.", index=result.index, dtype="string")

    sensitivity.loc[has_labor] = "spontaneous_labor_strict"
    note.loc[has_labor] = "PGADM contains 陣痛/破水/現血."

    non_spontaneous = ~has_labor & has_reason
    sensitivity.loc[non_spontaneous] = "induction_or_non_spontaneous_strict"
    note.loc[non_spontaneous] = "Reason of induction is non-missing and PGADM lacks 陣痛/破水/現血."

    mixed = has_labor & contains_terms(pgadm, INDUCTION_TERMS)
    note.loc[mixed] = "PGADM contains both labor symptom and induction term; strict rule keeps spontaneous but requires review."

    result["LABOR_ONSET_GROUP_SENSITIVITY"] = sensitivity
    result["LABOR_ONSET_VALIDATION_NOTE"] = note
    result["FLAG_LABOR_ONSET_REQUIRES_REVIEW"] = (
        sensitivity.eq("uncertain") | mixed | result["LABOR_ONSET_GROUP"].isna()
    ).astype("int64")
    return result


def classification_comparison(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    cross_tab = pd.crosstab(
        df["LABOR_ONSET_GROUP"],
        df["LABOR_ONSET_GROUP_SENSITIVITY"],
        dropna=False,
    ).reset_index()

    original_counts = (
        df["LABOR_ONSET_GROUP"]
        .astype("string")
        .fillna("<MISSING>")
        .value_counts(dropna=False)
        .rename_axis("LABOR_ONSET_GROUP")
        .reset_index(name="count")
    )
    original_counts["pct"] = original_counts["count"] / len(df) if len(df) else np.nan

    sensitivity_counts = (
        df["LABOR_ONSET_GROUP_SENSITIVITY"]
        .astype("string")
        .fillna("<MISSING>")
        .value_counts(dropna=False)
        .rename_axis("LABOR_ONSET_GROUP_SENSITIVITY")
        .reset_index(name="count")
    )
    sensitivity_counts["pct"] = sensitivity_counts["count"] / len(df) if len(df) else np.nan

    normalized_original = df["LABOR_ONSET_GROUP"].map(
        {
            "spontaneous_labor": "spontaneous_labor_strict",
            "non_spontaneous_or_induction": "induction_or_non_spontaneous_strict",
            "uncertain": "uncertain",
        }
    )
    disagreement = df[normalized_original.ne(df["LABOR_ONSET_GROUP_SENSITIVITY"])].copy()
    uncertainty = df[df["LABOR_ONSET_GROUP_SENSITIVITY"].eq("uncertain")].copy()

    review_cols = [
        "DELIVERY_TIME",
        "PGADM",
        "Reason of induction",
        "LABOR_ONSET_GROUP",
        "LABOR_ONSET_GROUP_SENSITIVITY",
        "LABOR_ONSET_VALIDATION_NOTE",
        "FLAG_LABOR_ONSET_REQUIRES_REVIEW",
        "DELIVER_MODE",
        "GESTAT_WEEKS_DECIMAL",
        "STAGE1_MINS",
        "STAGE2_MINS_CLEAN",
    ]
    review_cols = [col for col in review_cols if col in df.columns]
    return {
        "cross_tab": cross_tab,
        "original_counts": original_counts,
        "sensitivity_counts": sensitivity_counts,
        "disagreement_cases": disagreement[review_cols],
        "uncertainty_cases": uncertainty[review_cols],
    }


def manual_review_sample(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    review_cols = [
        "DELIVERY_TIME",
        "PGADM",
        "Reason of induction",
        "DELIVER_MODE",
        "GESTAT_WEEKS_DECIMAL",
        "STAGE1_MINS",
        "STAGE2_MINS_CLEAN",
        "LABOR_ONSET_GROUP",
        "LABOR_ONSET_GROUP_SENSITIVITY",
        "LABOR_ONSET_VALIDATION_NOTE",
        "FLAG_LABOR_ONSET_REQUIRES_REVIEW",
    ]
    review_cols = [col for col in review_cols if col in df.columns]

    uncertain = df[df["LABOR_ONSET_GROUP_SENSITIVITY"].eq("uncertain")].copy()
    if len(uncertain) > 100:
        sample = uncertain.sample(n=100, random_state=20260526)
        strategy = "Random sample of 100 uncertain cases."
    elif len(uncertain) > 0:
        sample = uncertain
        strategy = "All uncertain cases."
    else:
        spontaneous = df[df["LABOR_ONSET_GROUP"].eq("spontaneous_labor")].sample(
            n=min(50, int(df["LABOR_ONSET_GROUP"].eq("spontaneous_labor").sum())),
            random_state=20260526,
        )
        non_spontaneous = df[df["LABOR_ONSET_GROUP"].eq("non_spontaneous_or_induction")].sample(
            n=min(50, int(df["LABOR_ONSET_GROUP"].eq("non_spontaneous_or_induction").sum())),
            random_state=20260527,
        )
        sample = pd.concat([spontaneous, non_spontaneous], ignore_index=True)
        strategy = "No uncertain cases; sampled 50 spontaneous_labor and 50 non_spontaneous_or_induction cases."

    summary = pd.DataFrame(
        [
            {
                "uncertain_case_count": len(uncertain),
                "sample_count": len(sample),
                "sampling_strategy": strategy,
            }
        ]
    )
    return {"sample_summary": summary, "manual_review_sample": sample[review_cols]}


def main() -> None:
    ensure_dirs()
    analysis_v01 = read_analysis_v01()
    analysis_v02 = create_sensitivity_classification(analysis_v01)

    write_excel(OUTPUT_DIR / "25_pgadm_value_audit.xlsx", {"pgadm_value_audit": pgadm_value_audit(analysis_v01)})
    write_excel(
        OUTPUT_DIR / "26_reason_of_induction_audit.xlsx",
        {"reason_of_induction_audit": reason_of_induction_audit(analysis_v01)},
    )
    write_excel(ANALYSIS_V02_FILE, {"analysis_variables_v02": analysis_v02})
    write_excel(
        OUTPUT_DIR / "27_labor_onset_classification_comparison.xlsx",
        classification_comparison(analysis_v02),
    )
    write_excel(
        OUTPUT_DIR / "28_labor_onset_manual_review_sample.xlsx",
        manual_review_sample(analysis_v02),
    )

    print("Labor onset classification validation completed.")
    print(f"Rows preserved: {len(analysis_v02)}")
    print(f"Sensitivity dataset: {ANALYSIS_V02_FILE}")
    print(
        "Sensitivity uncertain cases: "
        f"{int(analysis_v02['LABOR_ONSET_GROUP_SENSITIVITY'].eq('uncertain').sum())}"
    )
    print(
        "Requires review cases: "
        f"{int(analysis_v02['FLAG_LABOR_ONSET_REQUIRES_REVIEW'].sum())}"
    )


if __name__ == "__main__":
    main()
