from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTERIM_FILE = PROJECT_ROOT / "data" / "interim" / "delivery_mode_interim_v01.xlsx"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

PROCESSED_FILE = PROCESSED_DIR / "delivery_mode_processed_candidate_v01.xlsx"
COHORT_OVERVIEW_FILE = OUTPUT_DIR / "14_cohort_overview.xlsx"
RECOMMENDATIONS_FILE = OUTPUT_DIR / "15_cohort_recommendations.xlsx"
BLUEPRINT_FILE = OUTPUT_DIR / "16_analysis_dataset_blueprint.xlsx"


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_interim() -> pd.DataFrame:
    if not INTERIM_FILE.exists():
        raise FileNotFoundError(
            f"Interim dataset not found: {INTERIM_FILE}. Run scripts/03_rule_based_cleaning_framework.py first."
        )
    return pd.read_excel(INTERIM_FILE, sheet_name="interim_v01")


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


def flag(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype("int64")


def value_distribution(df: pd.DataFrame, column: str) -> pd.DataFrame:
    series = df[column]
    counts = series.astype("string").fillna("<MISSING>").value_counts(dropna=False)
    return pd.DataFrame(
        {
            "variable": column,
            "value": counts.index.astype(str),
            "count": counts.to_numpy(),
            "pct": counts.to_numpy() / len(df) if len(df) else np.nan,
        }
    )


def numeric_distribution(df: pd.DataFrame, column: str) -> pd.DataFrame:
    series = numeric(df, column)
    summary = series.describe(percentiles=[0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return summary.to_frame("value").reset_index(names="statistic").assign(variable=column)[
        ["variable", "statistic", "value"]
    ]


def missingness_pattern(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for column in df.columns:
        missing_count = int(df[column].isna().sum())
        records.append(
            {
                "variable": column,
                "missing_count": missing_count,
                "missing_pct": missing_count / len(df) if len(df) else np.nan,
                "non_missing_count": int(df[column].notna().sum()),
            }
        )
    return pd.DataFrame(records).sort_values(["missing_count", "variable"], ascending=[False, True])


def epidural_distribution(df: pd.DataFrame) -> pd.DataFrame:
    records = []
    for column in ["EPA timing", "EPA time", "PAIN"]:
        if column not in df.columns:
            continue
        dist = value_distribution(df, column)
        dist["interpretation_note"] = (
            "Potential epidural-related field; confirm source definition before modeling."
        )
        records.append(dist)
    if not records:
        return pd.DataFrame(columns=["variable", "value", "count", "pct", "interpretation_note"])
    return pd.concat(records, ignore_index=True)


def cohort_overview(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "delivery_mode": value_distribution(df, "DELIVER_MODE"),
        "gestational_age": numeric_distribution(df, "GESTAT_WEEKS_DECIMAL"),
        "maternal_age": numeric_distribution(df, "Age"),
        "birth_weight": numeric_distribution(df, "BIRTH_WEIGHT"),
        "parity": value_distribution(df, "PARA"),
        "epidural_usage": epidural_distribution(df),
        "missingness_pattern": missingness_pattern(df),
    }


def add_exclusion_flags(df: pd.DataFrame) -> pd.DataFrame:
    processed = df.copy()

    gestat = numeric(processed, "GESTAT_WEEKS_DECIMAL")
    birth_weight = numeric(processed, "BIRTH_WEIGHT")
    maternal_age = numeric(processed, "Age")

    key_outcomes = ["BIRTH_WEIGHT", "A_S_1", "A_S_5"]
    missing_key_outcome = processed[key_outcomes].isna().any(axis=1)

    processed["FLAG_PRETERM"] = flag(gestat < 37)
    processed["FLAG_POSTTERM"] = flag(gestat >= 42)
    processed["FLAG_EXTREME_BIRTH_WEIGHT"] = flag((birth_weight < 500) | (birth_weight > 5000))
    processed["FLAG_EXTREME_MATERNAL_AGE"] = flag((maternal_age < 12) | (maternal_age > 60))
    processed["FLAG_MISSING_DELIVERY_MODE"] = flag(processed["DELIVER_MODE"].isna())
    processed["FLAG_MISSING_KEY_OUTCOME"] = flag(missing_key_outcome)

    return processed


def cohort_recommendations(processed: pd.DataFrame) -> pd.DataFrame:
    total = len(processed)
    rows = [
        {
            "potential_exclusion": "Preterm gestation",
            "flag": "FLAG_PRETERM",
            "rationale": "Gestational age < 37 weeks may represent a clinically different population.",
            "possible_bias_concern": "Excluding preterm births may limit generalizability and remove high-risk pregnancies.",
            "recommendation_level": "optional",
        },
        {
            "potential_exclusion": "Postterm gestation",
            "flag": "FLAG_POSTTERM",
            "rationale": "Gestational age >= 42 weeks may represent a distinct clinical subgroup.",
            "possible_bias_concern": "May remove clinically important postterm management patterns.",
            "recommendation_level": "optional",
        },
        {
            "potential_exclusion": "Extreme birth weight",
            "flag": "FLAG_EXTREME_BIRTH_WEIGHT",
            "rationale": "Birth weight < 500 g or > 5000 g may be data error or a rare clinical subgroup.",
            "possible_bias_concern": "Could exclude valid extreme neonatal outcomes if applied without chart review.",
            "recommendation_level": "avoid exclusion",
        },
        {
            "potential_exclusion": "Extreme maternal age",
            "flag": "FLAG_EXTREME_MATERNAL_AGE",
            "rationale": "Maternal age < 12 or > 60 is outside usual obstetric range and may indicate data entry error.",
            "possible_bias_concern": "Very low expected impact; review records before exclusion.",
            "recommendation_level": "recommended",
        },
        {
            "potential_exclusion": "Missing delivery mode",
            "flag": "FLAG_MISSING_DELIVERY_MODE",
            "rationale": "Delivery mode is the likely primary exposure and is required for exposure-defined analyses.",
            "possible_bias_concern": "If missingness is related to clinical workflow, exclusion may introduce selection bias.",
            "recommendation_level": "recommended",
        },
        {
            "potential_exclusion": "Missing key neonatal outcome",
            "flag": "FLAG_MISSING_KEY_OUTCOME",
            "rationale": "Birth weight and Apgar scores are likely primary or secondary outcomes.",
            "possible_bias_concern": "Complete-case outcome analysis can bias estimates if outcome missingness is informative.",
            "recommendation_level": "optional",
        },
    ]

    for row in rows:
        count = int(processed[row["flag"]].sum())
        row["affected_n"] = count
        row["affected_pct"] = count / total if total else np.nan

    return pd.DataFrame(rows)[
        [
            "potential_exclusion",
            "rationale",
            "affected_n",
            "affected_pct",
            "possible_bias_concern",
            "recommendation_level",
            "flag",
        ]
    ]


def variable_blueprint(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        ("DELIVER_MODE", "exposure", "Primary delivery mode exposure", "category/string", "Confirm codebook; encode as categorical indicators if modeling."),
        ("BIRTH_WEIGHT", "outcome", "Primary neonatal continuous outcome candidate", "numeric", "Use raw grams; assess linearity and outliers."),
        ("A_S_1", "outcome", "Apgar score at 1 minute", "integer", "Consider ordinal or binary low Apgar threshold after clinical input."),
        ("A_S_5", "outcome", "Apgar score at 5 minutes", "integer", "Consider ordinal or binary low Apgar threshold after clinical input."),
        ("BIRTH_LENGTH", "outcome", "Neonatal birth length", "numeric", "Use as secondary neonatal outcome."),
        ("GESTAT_WEEKS_DECIMAL", "covariate", "Gestational age in decimal weeks", "numeric", "Use derived value; keep original gestational fields."),
        ("Age", "covariate", "Maternal age", "numeric", "Use continuous or clinically defined age bands."),
        ("PARA", "covariate", "Parity", "integer/category", "Consider nulliparous vs multiparous derived grouping."),
        ("GRAVIDA", "covariate", "Gravidity", "integer/category", "Check consistency with parity before modeling."),
        ("BMI", "covariate", "Maternal BMI", "numeric", "Consider WHO or obstetric BMI categories after review."),
        ("PGADM", "covariate", "Admission or pregnancy-related category", "category/string", "Do not recode until codebook confirmed."),
        ("EDUCATION", "covariate", "Maternal education", "category/string", "Confirm ordinal coding before trend modeling."),
        ("MARRIAGE", "covariate", "Marital status", "category/string", "Confirm nominal coding."),
        ("EPA timing", "covariate", "Potential epidural timing category", "category/string", "Confirm epidural definition and timing relation."),
        ("EPA time", "covariate", "Potential epidural timestamp", "datetime", "Use only after confirming epidural data source."),
        ("PAIN", "covariate", "Potential analgesia or pain-related timestamp/field", "datetime/string", "Definition unclear; clinician/database review required."),
        ("PARTO_NO", "identifier", "Delivery or parturition identifier", "string/integer", "Use for traceability, not as model predictor."),
        ("BABY_NO", "identifier", "Baby identifier", "string/integer", "Use for neonatal record linkage."),
        ("CHART", "identifier", "Maternal chart identifier", "string/integer", "Use for duplicate and clustering checks."),
        ("ACC_NO", "identifier", "Encounter/account identifier", "string/integer", "Use for traceability and encounter-level checks."),
        ("STAGE1_MINS_CLEAN", "derived variable", "Not yet created; first stage clean candidate", "numeric", "Do not create final clean value until extreme values reviewed."),
        ("STAGE2_MINS_CLEAN", "derived variable", "Second stage duration with -1 set to missing", "numeric", "Use with FLAG_STAGE2_NEGATIVE and FLAG_STAGE2_EXTREME sensitivity checks."),
        ("FLAG_PRETERM", "exclusion", "Gestational age < 37 weeks", "binary integer", "Use as subgroup or optional exclusion."),
        ("FLAG_POSTTERM", "exclusion", "Gestational age >= 42 weeks", "binary integer", "Use as subgroup or optional exclusion."),
        ("FLAG_EXTREME_BIRTH_WEIGHT", "exclusion", "Birth weight < 500 or > 5000", "binary integer", "Avoid automatic exclusion without validation."),
        ("FLAG_EXTREME_MATERNAL_AGE", "exclusion", "Maternal age < 12 or > 60", "binary integer", "Review and consider exclusion if data entry error confirmed."),
        ("FLAG_MISSING_DELIVERY_MODE", "exclusion", "Missing primary exposure", "binary integer", "Recommended exclusion for exposure-defined primary analysis."),
        ("FLAG_MISSING_KEY_OUTCOME", "exclusion", "Missing birth weight or Apgar scores", "binary integer", "Use outcome-specific complete-case logic."),
    ]

    records = []
    for variable, category, role, dtype, transform in rows:
        records.append(
            {
                "variable_name": variable,
                "present_in_dataset": variable in df.columns,
                "variable_category": category,
                "suggested_variable_role": role,
                "recommended_datatype": dtype,
                "suggested_transformation": transform,
            }
        )
    return pd.DataFrame(records)


def main() -> None:
    ensure_dirs()
    interim = read_interim()
    processed = add_exclusion_flags(interim)

    write_excel(COHORT_OVERVIEW_FILE, cohort_overview(interim))
    write_excel(RECOMMENDATIONS_FILE, {"recommendations": cohort_recommendations(processed)})
    write_excel(BLUEPRINT_FILE, {"analysis_dataset_blueprint": variable_blueprint(processed)})
    write_excel(PROCESSED_FILE, {"processed_candidate_v01": processed})

    print("Analysis cohort framework completed.")
    print(f"Rows preserved: {len(processed)}")
    print(f"Interim columns: {len(interim.columns)}")
    print(f"Processed candidate columns: {len(processed.columns)}")
    print(f"Processed candidate: {PROCESSED_FILE}")


if __name__ == "__main__":
    main()
