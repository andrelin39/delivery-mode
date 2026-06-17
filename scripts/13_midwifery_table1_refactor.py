from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v03.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "manuscript_table1_midwifery.xlsx"

TABLE_TITLE = (
    "Characteristics of women according to labor admission pathway during a strict "
    "COVID-19 admission management period"
)

GROUP_ORDER = ["spontaneous_labor", "non_spontaneous_or_induction"]
GROUP_LABELS = {
    "spontaneous_labor": "Symptomatic admission",
    "non_spontaneous_or_induction": "Planned induction admission",
}

CONTINUOUS_VARIABLES = [
    ("Maternal characteristics", "Maternal age, years", "Age"),
    ("Maternal characteristics", "Body mass index, kg/m²", "BMI"),
    ("Maternal characteristics", "Gravidity", "GRAVIDA"),
    ("Maternal characteristics", "Parity", "PARA"),
    ("Pregnancy characteristics", "Gestational age at delivery, weeks", "GESTAT_WEEKS_DECIMAL"),
    ("Pregnancy characteristics", "Birth weight, g", "BIRTH_WEIGHT"),
]
CATEGORICAL_VARIABLES = [
    ("Maternal characteristics", "Marriage status", "MARRIAGE"),
    ("Maternal characteristics", "Education level", "EDUCATION"),
]
TABLE_VARIABLES = [
    ("continuous", "Maternal characteristics", "Maternal age, years", "Age"),
    ("continuous", "Maternal characteristics", "Body mass index, kg/m²", "BMI"),
    ("continuous", "Maternal characteristics", "Gravidity", "GRAVIDA"),
    ("continuous", "Maternal characteristics", "Parity", "PARA"),
    ("categorical", "Maternal characteristics", "Marriage status", "MARRIAGE"),
    ("categorical", "Maternal characteristics", "Education level", "EDUCATION"),
    ("continuous", "Pregnancy characteristics", "Gestational age at delivery, weeks", "GESTAT_WEEKS_DECIMAL"),
    ("continuous", "Pregnancy characteristics", "Birth weight, g", "BIRTH_WEIGHT"),
]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_v03() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"v03 dataset not found: {DATA_FILE}")
    return pd.read_excel(DATA_FILE, sheet_name="analysis_variables_v03")


def make_table_dataset(df: pd.DataFrame) -> pd.DataFrame:
    required = {"LABOR_ONSET_GROUP", "COVID_POLICY_PERIOD_FINAL"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"Required columns not found: {sorted(missing)}")

    strict = df[df["COVID_POLICY_PERIOD_FINAL"].astype("string").eq("strict_covid_policy_period")].copy()
    strict = strict[strict["LABOR_ONSET_GROUP"].astype("string").isin(GROUP_ORDER)].copy()

    for _, _, col in CONTINUOUS_VARIABLES:
        strict[col] = pd.to_numeric(strict[col], errors="coerce")
    for _, _, col in CATEGORICAL_VARIABLES:
        strict[col] = strict[col].astype("string")

    strict["LABOR_ONSET_GROUP"] = pd.Categorical(
        strict["LABOR_ONSET_GROUP"],
        categories=GROUP_ORDER,
        ordered=True,
    )
    return strict


def validate_cohort(df: pd.DataFrame) -> None:
    """Abort if hidden exclusions or category-count mismatches are detected."""
    n = len(df)

    if "FLAG_LABOR_ONSET_REQUIRES_REVIEW" in df.columns:
        n_flagged = int(df["FLAG_LABOR_ONSET_REQUIRES_REVIEW"].eq(1).sum())
        if n_flagged == 0:
            raise ValueError(
                "No FLAG_LABOR_ONSET_REQUIRES_REVIEW==1 records in cohort — "
                "a sensitivity-analysis exclusion may have been applied unintentionally."
            )

    for _, label, col in CATEGORICAL_VARIABLES:
        n_notna = int(df[col].notna().sum())
        group_sum = sum(
            int(df.loc[df["LABOR_ONSET_GROUP"].astype("string").eq(g), col].notna().sum())
            for g in GROUP_ORDER
        )
        if group_sum != n_notna:
            raise ValueError(
                f"Categorical mismatch for '{label}': "
                f"group-level non-missing sum={group_sum}, total non-missing={n_notna}. "
                f"Implicit exclusion detected — check cohort source."
            )


def fmt_p(value: float) -> str:
    if pd.isna(value):
        return ""
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def fmt_cont(series: pd.Series) -> str:
    x = pd.to_numeric(series, errors="coerce").dropna()
    if x.empty:
        return ""
    return f"{x.mean():.2f} ± {x.std(ddof=1):.2f}"


def fmt_cat(count: int, denominator: int) -> str:
    if denominator == 0:
        return f"{count} ()"
    return f"{count} ({count / denominator * 100:.1f}%)"


def continuous_p_value(df: pd.DataFrame, col: str) -> float:
    groups = [
        pd.to_numeric(
            df.loc[df["LABOR_ONSET_GROUP"].astype("string").eq(group), col],
            errors="coerce",
        ).dropna()
        for group in GROUP_ORDER
    ]
    if any(len(group) < 2 for group in groups):
        return np.nan
    return float(stats.ttest_ind(groups[0], groups[1], equal_var=False).pvalue)


def categorical_p_value(df: pd.DataFrame, col: str) -> float:
    valid = df[df[col].notna()].copy()
    if valid.empty:
        return np.nan
    table = pd.crosstab(valid[col], valid["LABOR_ONSET_GROUP"]).reindex(columns=GROUP_ORDER, fill_value=0)
    if table.shape[0] < 2 or table.shape[1] < 2:
        return np.nan
    return float(stats.chi2_contingency(table, correction=False).pvalue)


def add_section_row(rows: list[dict[str, Any]], section: str) -> None:
    rows.append(
        {
            "Section": section,
            "Characteristic": "",
            "Category": "",
            "Missing n": "",
            "Total": "",
            GROUP_LABELS[GROUP_ORDER[0]]: "",
            GROUP_LABELS[GROUP_ORDER[1]]: "",
            "P value": "",
        }
    )


def build_table1(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    current_section = ""

    group_frames = {
        group: df[df["LABOR_ONSET_GROUP"].astype("string").eq(group)] for group in GROUP_ORDER
    }

    for var_type, section, label, col in TABLE_VARIABLES:
        if section != current_section:
            add_section_row(rows, section)
            current_section = section

        if var_type == "continuous":
            p_value = continuous_p_value(df, col)
            row = {
                "Section": "",
                "Characteristic": label,
                "Category": "",
                "Missing n": int(df[col].isna().sum()),
                "Total": fmt_cont(df[col]),
                GROUP_LABELS[GROUP_ORDER[0]]: fmt_cont(group_frames[GROUP_ORDER[0]][col]),
                GROUP_LABELS[GROUP_ORDER[1]]: fmt_cont(group_frames[GROUP_ORDER[1]][col]),
                "P value": fmt_p(p_value),
            }
            rows.append(row)
            continue

        series = df[col].dropna().astype("string")
        categories = sorted(series.unique().tolist())
        p_value = categorical_p_value(df, col)
        missing_n = int(df[col].isna().sum())
        for idx, category in enumerate(categories):
            row = {
                "Section": "",
                "Characteristic": label if idx == 0 else "",
                "Category": category,
                "Missing n": missing_n if idx == 0 else "",
                "Total": fmt_cat(int(df[col].astype("string").eq(category).sum()), int(df[col].notna().sum())),
                "P value": fmt_p(p_value) if idx == 0 else "",
            }
            for group in GROUP_ORDER:
                subset = group_frames[group]
                denominator = int(subset[col].notna().sum())
                count = int(subset[col].astype("string").eq(category).sum())
                row[GROUP_LABELS[group]] = fmt_cat(count, denominator)
            rows.append(row)

    return pd.DataFrame(rows)


def build_metadata(df: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    missing_rows = []
    for _, label, col in [*CONTINUOUS_VARIABLES, *CATEGORICAL_VARIABLES]:
        missing_rows.append({"Characteristic": label, "Missing n": int(df[col].isna().sum())})
    significant = table[
        pd.to_numeric(table["P value"].replace({"<0.001": "0.0005", "": np.nan}), errors="coerce") < 0.05
    ]["Characteristic"].replace("", pd.NA).dropna().tolist()
    return pd.DataFrame(
        [
            {"Item": "Source file", "Value": str(DATA_FILE.relative_to(PROJECT_ROOT))},
            {"Item": "Study context", "Value": "strict_covid_policy_period"},
            {"Item": "Total n", "Value": len(df)},
            {"Item": GROUP_LABELS[GROUP_ORDER[0]], "Value": int(df["LABOR_ONSET_GROUP"].astype("string").eq(GROUP_ORDER[0]).sum())},
            {"Item": GROUP_LABELS[GROUP_ORDER[1]], "Value": int(df["LABOR_ONSET_GROUP"].astype("string").eq(GROUP_ORDER[1]).sum())},
            {"Item": "Any missing data in retained variables", "Value": any(item["Missing n"] > 0 for item in missing_rows)},
            {"Item": "Characteristics with p < 0.05", "Value": ", ".join(significant) if significant else "None"},
        ]
    )


def write_excel(table: pd.DataFrame, metadata: pd.DataFrame) -> None:
    try:
        writer = pd.ExcelWriter(OUTPUT_FILE, engine="xlsxwriter")
    except ModuleNotFoundError:
        writer = pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl")

    with writer:
        table.to_excel(writer, sheet_name="Table 1", startrow=2, index=False)
        metadata.to_excel(writer, sheet_name="Metadata", index=False)
        footnotes = pd.DataFrame(
            {
                "Footnote": [
                    "Continuous variables are shown as mean ± SD.",
                    "Categorical variables are shown as n (%).",
                    "P values were calculated using Welch t tests for continuous variables and chi-square tests for categorical variables.",
                    "The strict COVID-19 admission management period was used as the study context.",
                ]
            }
        )
        footnotes.to_excel(writer, sheet_name="Footnotes", index=False)

        workbook = writer.book
        worksheet = writer.sheets["Table 1"]
        worksheet.write(0, 0, TABLE_TITLE)
        if hasattr(workbook, "add_format"):
            title_fmt = workbook.add_format({"bold": True, "font_size": 12})
            header_fmt = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
            section_fmt = workbook.add_format({"bold": True, "bg_color": "#EEEEEE"})
            worksheet.write(0, 0, TABLE_TITLE, title_fmt)
            for col_idx, value in enumerate(table.columns):
                worksheet.write(2, col_idx, value, header_fmt)
            for row_idx, row in table.iterrows():
                if row["Section"]:
                    worksheet.set_row(row_idx + 3, None, section_fmt)
            worksheet.set_column(0, 0, 24)
            worksheet.set_column(1, 1, 36)
            worksheet.set_column(2, 2, 18)
            worksheet.set_column(3, 7, 24)


def main() -> None:
    ensure_dirs()
    df = make_table_dataset(read_v03())
    validate_cohort(df)
    table = build_table1(df)
    metadata = build_metadata(df, table)
    write_excel(table, metadata)

    n_total = len(df)
    group_counts = {
        GROUP_LABELS[g]: int(df["LABOR_ONSET_GROUP"].astype("string").eq(g).sum())
        for g in GROUP_ORDER
    }
    n_flagged = (
        int(df["FLAG_LABOR_ONSET_REQUIRES_REVIEW"].eq(1).sum())
        if "FLAG_LABOR_ONSET_REQUIRES_REVIEW" in df.columns
        else "n/a"
    )

    print(f"wrote: {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"\n=== Cohort validation ===")
    print(f"N total                              : {n_total}")
    for label, count in group_counts.items():
        print(f"  {label}: {count}")
    print(f"FLAG_LABOR_ONSET_REQUIRES_REVIEW==1  : {n_flagged} (retained)")
    print(f"\n=== Categorical variable validation ===")
    all_pass = True
    for _, label, col in CATEGORICAL_VARIABLES:
        n_notna = int(df[col].notna().sum())
        n_miss = n_total - n_notna
        group_sum = sum(
            int(df.loc[df["LABOR_ONSET_GROUP"].astype("string").eq(g), col].notna().sum())
            for g in GROUP_ORDER
        )
        status = "OK" if group_sum == n_notna else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  [{status}] {label}: non-missing={n_notna}, group_sum={group_sum}, missing={n_miss}")
    if all_pass:
        print("All categorical variables account for the full analytic cohort.")


if __name__ == "__main__":
    main()
