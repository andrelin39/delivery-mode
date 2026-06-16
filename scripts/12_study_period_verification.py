from __future__ import annotations

from pathlib import Path

import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v03.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
OUTPUT_EXCEL = OUTPUT_DIR / "43_study_period_verification.xlsx"
OUTPUT_FIG = OUTPUT_DIR / "fig_monthly_case_distribution.png"

PRE_POLICY_END = pd.Timestamp("2021-05-16")
STRICT_POLICY_START = pd.Timestamp("2021-05-17")
STRICT_POLICY_END = pd.Timestamp("2023-03-19")
RELAXATION_START = pd.Timestamp("2023-03-20")

POLICY_PERIOD_ORDER = [
    "pre_policy_period",
    "strict_policy_period",
    "policy_relaxation_period",
]
YEARS_TO_REPORT = [2021, 2022, 2023]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def read_analysis_v03() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Analysis v03 dataset not found: {DATA_FILE}")
    return pd.read_excel(DATA_FILE, sheet_name="analysis_variables_v03")


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    try:
        writer = pd.ExcelWriter(path, engine="xlsxwriter")
    except ModuleNotFoundError:
        writer = pd.ExcelWriter(path, engine="openpyxl")
    with writer:
        for sheet_name, data in sheets.items():
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def classify_policy_period(delivery_dates: pd.Series) -> pd.Series:
    dates = pd.to_datetime(delivery_dates, errors="coerce").dt.normalize()
    period = pd.Series(pd.NA, index=dates.index, dtype="string")
    period.loc[dates.le(PRE_POLICY_END)] = "pre_policy_period"
    period.loc[dates.ge(STRICT_POLICY_START) & dates.le(STRICT_POLICY_END)] = "strict_policy_period"
    period.loc[dates.ge(RELAXATION_START)] = "policy_relaxation_period"
    return period


def format_date(value: pd.Timestamp | pd.NaT) -> str:
    if pd.isna(value):
        return "NA"
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def build_monthly_figure(month_distribution: pd.DataFrame) -> None:
    plot_df = month_distribution.copy()
    plot_df["month_start"] = pd.to_datetime(plot_df["YYYY-MM"] + "-01")

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(plot_df["month_start"], plot_df["n"], width=24, color="#4C78A8")
    ax.set_title("Monthly Case Distribution")
    ax.set_xlabel("Delivery month")
    ax.set_ylabel("Number of cases")
    ax.grid(axis="y", alpha=0.25)
    fig.autofmt_xdate(rotation=45)
    fig.tight_layout()
    fig.savefig(OUTPUT_FIG, dpi=300)
    plt.close(fig)


def main() -> None:
    ensure_dirs()
    df = read_analysis_v03()

    if "DELIVERY_TIME" not in df.columns:
        raise KeyError("DELIVERY_TIME column not found in analysis v03 dataset.")

    delivery_time = pd.to_datetime(df["DELIVERY_TIME"], errors="coerce")
    valid_delivery_time = delivery_time.dropna()
    earliest = valid_delivery_time.min()
    latest = valid_delivery_time.max()

    year_distribution = (
        delivery_time.dt.year.value_counts(dropna=False).rename_axis("year").reset_index(name="n")
    )
    year_distribution = (
        pd.DataFrame({"year": YEARS_TO_REPORT})
        .merge(year_distribution.dropna(), on="year", how="left")
        .fillna({"n": 0})
    )
    year_distribution["year"] = year_distribution["year"].astype(int)
    year_distribution["n"] = year_distribution["n"].astype(int)

    month_distribution = (
        delivery_time.dt.to_period("M")
        .astype("string")
        .value_counts(dropna=False)
        .rename_axis("YYYY-MM")
        .reset_index(name="n")
    )
    month_distribution = month_distribution[month_distribution["YYYY-MM"].ne("<NA>")]
    month_distribution = month_distribution.sort_values("YYYY-MM").reset_index(drop=True)

    recalculated_policy_period = classify_policy_period(delivery_time)
    policy_period_distribution = (
        recalculated_policy_period.value_counts(dropna=False)
        .rename_axis("policy_period_recalculated")
        .reset_index(name="n")
    )
    policy_period_distribution = (
        pd.DataFrame({"policy_period_recalculated": POLICY_PERIOD_ORDER})
        .merge(policy_period_distribution, on="policy_period_recalculated", how="left")
        .fillna({"n": 0})
    )
    policy_period_distribution["n"] = policy_period_distribution["n"].astype(int)

    existing_policy_col = None
    for candidate in ["COVID_POLICY_PERIOD_FINAL", "COVID_POLICY_PERIOD"]:
        if candidate in df.columns:
            existing_policy_col = candidate
            break

    if existing_policy_col:
        existing_policy = df[existing_policy_col].astype("string")
        comparable_existing_policy = existing_policy.replace(
            {"strict_covid_policy_period": "strict_policy_period"}
        )
        mismatch = (
            comparable_existing_policy.notna()
            & recalculated_policy_period.notna()
            & comparable_existing_policy.ne(recalculated_policy_period)
        )
        existing_distribution = (
            comparable_existing_policy.value_counts(dropna=False)
            .rename_axis("policy_period_recalculated")
            .reset_index(name="existing_n")
        )
        policy_period_distribution = policy_period_distribution.merge(
            existing_distribution, on="policy_period_recalculated", how="left"
        ).fillna({"existing_n": 0})
        policy_period_distribution["existing_n"] = policy_period_distribution["existing_n"].astype(int)
        policy_period_distribution["existing_policy_column"] = existing_policy_col
        policy_period_distribution["mismatch_n_vs_existing"] = int(mismatch.sum())
    else:
        policy_period_distribution["existing_n"] = pd.NA
        policy_period_distribution["existing_policy_column"] = "not_found"
        policy_period_distribution["mismatch_n_vs_existing"] = pd.NA

    total_n = int(len(df))
    missing_delivery_time_n = int(delivery_time.isna().sum())
    irb_start = pd.Timestamp("2021-01-01")
    irb_end = pd.Timestamp("2022-12-31 23:59:59")
    irb_2021_01_to_2022_12_contains_data = bool(
        missing_delivery_time_n == 0 and earliest >= irb_start and latest <= irb_end
    )
    irb_2021_01_to_2022_12_exact_match = bool(
        missing_delivery_time_n == 0
        and earliest.to_period("M") == pd.Period("2021-01", freq="M")
        and latest.to_period("M") == pd.Period("2022-12", freq="M")
    )

    study_period_summary = pd.DataFrame(
        [
            {"metric": "source_file", "value": str(DATA_FILE.relative_to(PROJECT_ROOT))},
            {"metric": "total_n", "value": total_n},
            {"metric": "missing_delivery_time_n", "value": missing_delivery_time_n},
            {"metric": "earliest_delivery_time", "value": format_date(earliest)},
            {"metric": "latest_delivery_time", "value": format_date(latest)},
            {"metric": "irb_period_start", "value": "2021-01"},
            {"metric": "irb_period_end", "value": "2022-12"},
            {
                "metric": "actual_period_matches_irb_2021_01_to_2022_12",
                "value": irb_2021_01_to_2022_12_exact_match,
            },
            {
                "metric": "actual_period_is_within_irb_2021_01_to_2022_12",
                "value": irb_2021_01_to_2022_12_contains_data,
            },
        ]
    )

    build_monthly_figure(month_distribution)
    write_excel(
        OUTPUT_EXCEL,
        {
            "study_period_summary": study_period_summary,
            "year_distribution": year_distribution,
            "month_distribution": month_distribution,
            "policy_period_distribution": policy_period_distribution,
        },
    )

    print(f"earliest_delivery_time: {format_date(earliest)}")
    print(f"latest_delivery_time: {format_date(latest)}")
    print("year_distribution:")
    print(year_distribution.to_string(index=False))
    print("policy_period_distribution:")
    print(policy_period_distribution.to_string(index=False))
    print(
        "actual_period_matches_irb_2021_01_to_2022_12: "
        f"{irb_2021_01_to_2022_12_exact_match}"
    )
    print(
        "actual_period_is_within_irb_2021_01_to_2022_12: "
        f"{irb_2021_01_to_2022_12_contains_data}"
    )
    print(f"wrote: {OUTPUT_EXCEL.relative_to(PROJECT_ROOT)}")
    print(f"wrote: {OUTPUT_FIG.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
