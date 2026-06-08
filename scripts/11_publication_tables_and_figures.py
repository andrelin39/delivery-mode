from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v03.xlsx"
RAW_FILE = PROJECT_ROOT / "rawdata_all.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DOCS_DIR = PROJECT_ROOT / "docs"

LABOR_ORDER = ["spontaneous_labor", "non_spontaneous_or_induction"]
LABOR_LABELS = {
    "spontaneous_labor": "Spontaneous labor",
    "non_spontaneous_or_induction": "Non-spontaneous/induction",
}
MODE_ORDER = ["NSD", "VED", "CS", "VBAC"]
COVARIATES = ["Age", "BMI", "GESTAT_WEEKS_DECIMAL", "BIRTH_WEIGHT", "GRAVIDA", "PARA"]
CONTINUOUS_TABLE1 = [
    "Age",
    "BMI",
    "GESTAT_WEEKS_DECIMAL",
    "BIRTH_WEIGHT",
    "BIRTH_LENGTH",
    "STAGE1_MINS",
    "STAGE2_MINS_CLEAN_FINAL",
    "A_S_1",
    "A_S_5",
]
CATEGORICAL_TABLE1 = [
    "DELIVERY_MODE_GROUP_FINAL",
    "CS_BINARY_FINAL",
    "OPERATIVE_DELIVERY_BINARY_FINAL",
    "EDUCATION",
    "MARRIAGE",
    "FLAG_STAGE1_EXTREME",
    "FLAG_STAGE2_EXTREME",
    "FLAG_LABOR_ONSET_REQUIRES_REVIEW",
]


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def read_v03() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"v03 dataset not found: {DATA_FILE}. Run script 10 first.")
    return pd.read_excel(DATA_FILE, sheet_name="analysis_variables_v03")


def write_excel(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    try:
        writer = pd.ExcelWriter(path, engine="xlsxwriter")
    except ModuleNotFoundError:
        writer = pd.ExcelWriter(path, engine="openpyxl")
    with writer:
        for sheet_name, data in sheets.items():
            data.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def fmt_num(value: float, digits: int = 2) -> str:
    if pd.isna(value):
        return "NA"
    return f"{value:.{digits}f}"


def fmt_p(value: float) -> str:
    if pd.isna(value):
        return "NA"
    if isinstance(value, str):
        return value
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def fmt_p_sentence(value: float) -> str:
    formatted = fmt_p(value)
    return "p < 0.001" if formatted == "<0.001" else f"p = {formatted}"


def fmt_cont(series: pd.Series) -> str:
    x = pd.to_numeric(series, errors="coerce").dropna()
    if len(x) == 0:
        return "NA"
    return f"{x.mean():.2f} ± {x.std():.2f}; {x.median():.2f} [{x.quantile(0.25):.2f}, {x.quantile(0.75):.2f}]"


def fmt_cat(count: int, denom: int) -> str:
    pct = count / denom * 100 if denom else np.nan
    return f"{count} ({pct:.1f}%)" if not pd.isna(pct) else f"{count} (NA)"


def make_analysis_df(df: pd.DataFrame) -> pd.DataFrame:
    strict = df[df["COVID_POLICY_PERIOD_FINAL"].astype("string").eq("strict_covid_policy_period")].copy()
    cols = [
        "LABOR_ONSET_GROUP_FINAL",
        "CS_BINARY_FINAL",
        "OPERATIVE_DELIVERY_BINARY_FINAL",
        "DELIVERY_MODE_GROUP_FINAL",
        "BIRTH_WEIGHT",
        "A_S_1",
        "A_S_5",
        "Age",
        "BMI",
        "GESTAT_WEEKS_DECIMAL",
        "GRAVIDA",
        "PARA",
        "FLAG_LABOR_ONSET_REQUIRES_REVIEW",
        "BIRTH_LENGTH",
        "STAGE1_MINS",
        "STAGE2_MINS_CLEAN_FINAL",
        "EDUCATION",
        "MARRIAGE",
        "FLAG_STAGE1_EXTREME",
        "FLAG_STAGE2_EXTREME",
    ]
    analysis = strict[[c for c in cols if c in strict.columns]].copy()
    for col in [
        "CS_BINARY_FINAL",
        "OPERATIVE_DELIVERY_BINARY_FINAL",
        "Age",
        "BMI",
        "GESTAT_WEEKS_DECIMAL",
        "GRAVIDA",
        "PARA",
        "BIRTH_WEIGHT",
        "BIRTH_LENGTH",
        "STAGE1_MINS",
        "STAGE2_MINS_CLEAN_FINAL",
        "A_S_1",
        "A_S_5",
        "FLAG_LABOR_ONSET_REQUIRES_REVIEW",
        "FLAG_STAGE1_EXTREME",
        "FLAG_STAGE2_EXTREME",
    ]:
        if col in analysis.columns:
            analysis[col] = pd.to_numeric(analysis[col], errors="coerce")
    analysis["LABOR_ONSET_GROUP_FINAL"] = pd.Categorical(analysis["LABOR_ONSET_GROUP_FINAL"], categories=LABOR_ORDER, ordered=True)
    return analysis


def table1(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    groups = [("Total", df), *[(LABOR_LABELS[g], df[df["LABOR_ONSET_GROUP_FINAL"].astype(str).eq(g)]) for g in LABOR_ORDER]]
    for var in CONTINUOUS_TABLE1:
        row = {"Variable": var, "Category": "", "Missing n": int(df[var].isna().sum())}
        for label, subset in groups:
            row[label] = fmt_cont(subset[var])
        rows.append(row)

    for var in CATEGORICAL_TABLE1:
        series = df[var].astype("string").fillna("<Missing>")
        if var == "DELIVERY_MODE_GROUP_FINAL":
            categories = [m for m in MODE_ORDER if m in set(series)]
        elif var in ["CS_BINARY_FINAL", "OPERATIVE_DELIVERY_BINARY_FINAL", "FLAG_STAGE1_EXTREME", "FLAG_STAGE2_EXTREME", "FLAG_LABOR_ONSET_REQUIRES_REVIEW"]:
            categories = ["0", "1"]
        else:
            categories = sorted(series.dropna().unique().tolist())
        for cat in categories:
            row = {"Variable": var, "Category": cat, "Missing n": int(df[var].isna().sum())}
            for label, subset in groups:
                sub_series = subset[var].astype("string").fillna("<Missing>")
                row[label] = fmt_cat(int(sub_series.eq(cat).sum()), len(subset))
            rows.append(row)

    footnotes = pd.DataFrame(
        {
            "Footnote": [
                "Continuous variables are shown as mean ± SD; median [IQR].",
                "Categorical variables are shown as n (%).",
                "CS = cesarean section; NSD = normal spontaneous delivery; VED = vacuum extraction delivery; VBAC = vaginal birth after cesarean.",
                "The strict COVID admission policy period is the study context and was not modeled as an exposure.",
            ]
        }
    )
    return {"Table 1": pd.DataFrame(rows), "Footnotes": footnotes}


def fit_logit(df: pd.DataFrame, predictors: list[str], model_name: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    data = df[["CS_BINARY_FINAL", "LABOR_ONSET_GROUP_FINAL", *predictors]].dropna().copy()
    data["labor_non_spontaneous_induction"] = data["LABOR_ONSET_GROUP_FINAL"].astype(str).eq("non_spontaneous_or_induction").astype(int)
    x_cols = ["labor_non_spontaneous_induction", *predictors]
    x = sm.add_constant(data[x_cols], has_constant="add").astype(float)
    y = data["CS_BINARY_FINAL"].astype(float)
    diagnostics = {
        "Model": model_name,
        "Model N": int(len(data)),
        "Event N": int(y.sum()),
        "Convergence status": "not_fit",
    }
    try:
        fitted = sm.Logit(y, x).fit(disp=False, maxiter=200)
        diagnostics["Convergence status"] = "converged" if fitted.mle_retvals.get("converged", False) else "not_converged"
        conf = fitted.conf_int()
        rows = []
        for term in fitted.params.index:
            if term == "const":
                continue
            rows.append(
                {
                    "Model": model_name,
                    "Term": term,
                    "OR": np.exp(fitted.params[term]),
                    "95% CI lower": np.exp(conf.loc[term, 0]),
                    "95% CI upper": np.exp(conf.loc[term, 1]),
                    "p-value": fitted.pvalues[term],
                    "Model N": diagnostics["Model N"],
                    "Event N": diagnostics["Event N"],
                    "Reference category": "Spontaneous labor" if term == "labor_non_spontaneous_induction" else "",
                    "Convergence status": diagnostics["Convergence status"],
                }
            )
        return pd.DataFrame(rows), diagnostics
    except Exception as exc:
        diagnostics["Convergence status"] = f"error: {exc}"
        return pd.DataFrame(), diagnostics


def table2(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    m1, d1 = fit_logit(df, [], "Model 1: unadjusted")
    m2, d2 = fit_logit(df, COVARIATES, "Model 2: adjusted")
    sens_df = df[df["FLAG_LABOR_ONSET_REQUIRES_REVIEW"].fillna(0).eq(0)].copy()
    m3, d3 = fit_logit(sens_df, COVARIATES, "Model 3: adjusted sensitivity excluding review-required cases")
    estimates = pd.concat([m1, m2, m3], ignore_index=True)
    display = estimates.copy()
    if not display.empty:
        display["OR (95% CI)"] = display.apply(
            lambda r: f"{r['OR']:.2f} ({r['95% CI lower']:.2f}, {r['95% CI upper']:.2f})", axis=1
        )
        display["p-value"] = display["p-value"].map(fmt_p)
    diagnostics = pd.DataFrame([d1, d2, d3])
    footnotes = pd.DataFrame(
        {
            "Footnote": [
                "Outcome: cesarean section versus non-cesarean birth.",
                "Primary contrast: non-spontaneous/induction versus spontaneous labor.",
                "Model 2 and Model 3 adjust for age, BMI, gestational weeks, birth weight, gravida, and para.",
            ]
        }
    )
    return {"Estimates": display, "Diagnostics": diagnostics, "Footnotes": footnotes}


def fit_binary_mode_contrast(df: pd.DataFrame, outcome: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    subset = df[df["DELIVERY_MODE_GROUP_FINAL"].astype("string").isin(["NSD", outcome])].copy()
    subset["_outcome"] = subset["DELIVERY_MODE_GROUP_FINAL"].astype(str).eq(outcome).astype(int)
    data = subset[["_outcome", "LABOR_ONSET_GROUP_FINAL", *COVARIATES]].dropna().copy()
    data["labor_non_spontaneous_induction"] = data["LABOR_ONSET_GROUP_FINAL"].astype(str).eq("non_spontaneous_or_induction").astype(int)
    x_cols = ["labor_non_spontaneous_induction", *COVARIATES]
    x = sm.add_constant(data[x_cols], has_constant="add").astype(float)
    y = data["_outcome"].astype(float)
    diagnostics = {"Outcome contrast": f"{outcome} vs NSD", "Model N": int(len(data)), "Convergence status": "not_fit"}
    try:
        fitted = sm.Logit(y, x).fit(disp=False, maxiter=200)
        diagnostics["Convergence status"] = "converged" if fitted.mle_retvals.get("converged", False) else "not_converged"
        conf = fitted.conf_int()
        rows = []
        for term in fitted.params.index:
            if term == "const":
                continue
            rows.append(
                {
                    "Outcome contrast": f"{outcome} vs NSD",
                    "Term": term,
                    "RRR": np.exp(fitted.params[term]),
                    "95% CI lower": np.exp(conf.loc[term, 0]),
                    "95% CI upper": np.exp(conf.loc[term, 1]),
                    "p-value": fitted.pvalues[term],
                    "Model N": diagnostics["Model N"],
                    "Convergence status": diagnostics["Convergence status"],
                }
            )
        return pd.DataFrame(rows), diagnostics
    except Exception as exc:
        diagnostics["Convergence status"] = f"error: {exc}"
        return pd.DataFrame(), diagnostics


def table3(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    modeled = df[df["DELIVERY_MODE_GROUP_FINAL"].astype("string").isin(["NSD", "VED", "CS"])].copy()
    modeled["mode_code"] = pd.Categorical(modeled["DELIVERY_MODE_GROUP_FINAL"], categories=["NSD", "VED", "CS"]).codes
    data = modeled[["mode_code", "LABOR_ONSET_GROUP_FINAL", *COVARIATES]].dropna().copy()
    data["labor_non_spontaneous_induction"] = data["LABOR_ONSET_GROUP_FINAL"].astype(str).eq("non_spontaneous_or_induction").astype(int)
    x_cols = ["labor_non_spontaneous_induction", *COVARIATES]
    x = sm.add_constant(data[x_cols], has_constant="add").astype(float)
    y = data["mode_code"]
    rows: list[dict[str, Any]] = []
    diagnostics = {
        "Model": "Multinomial logistic regression",
        "Model N": int(len(data)),
        "Reference outcome": "NSD",
        "Convergence status": "not_fit",
    }
    try:
        fitted = sm.MNLogit(y, x).fit(disp=False, maxiter=200)
        diagnostics["Convergence status"] = "converged" if fitted.mle_retvals.get("converged", False) else "not_converged"
        conf = fitted.conf_int()
        pvalues = fitted.pvalues
        outcome_map = {1: ("VED vs NSD", 0), 2: ("CS vs NSD", 1)}
        for outcome_code, (contrast, param_col) in outcome_map.items():
            for term in fitted.params.index:
                if term == "const":
                    continue
                conf_code = str(outcome_code)
                rows.append(
                    {
                        "Outcome contrast": contrast,
                        "Term": term,
                        "RRR": np.exp(fitted.params.loc[term, param_col]),
                        "95% CI lower": np.exp(conf.loc[(conf_code, term), "lower"]),
                        "95% CI upper": np.exp(conf.loc[(conf_code, term), "upper"]),
                        "p-value": pvalues.loc[term, param_col],
                        "Model N": diagnostics["Model N"],
                        "Convergence status": diagnostics["Convergence status"],
                    }
                )
    except Exception as exc:
        diagnostics["Convergence status"] = f"error: {exc}"
    estimates = pd.DataFrame(rows)
    display = estimates.copy()
    if not display.empty:
        display["RRR (95% CI)"] = display.apply(
            lambda r: f"{r['RRR']:.2f} ({r['95% CI lower']:.2f}, {r['95% CI upper']:.2f})", axis=1
        )
        display["p-value"] = display["p-value"].map(fmt_p)
    footnotes = [
        "Reference outcome: NSD.",
        "RRR = relative risk ratio from multinomial logistic regression.",
    ]
    if int(df["DELIVERY_MODE_GROUP_FINAL"].astype("string").eq("VBAC").sum()) == 0:
        footnotes.append("VBAC was retained in the data dictionary but not modeled separately because no VBAC cases were observed.")
    return {"Estimates": display, "Diagnostics": pd.DataFrame([diagnostics]), "Footnotes": pd.DataFrame({"Footnote": footnotes})}


def secondary_outcomes_table(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    profiled = df.copy()
    profiled["LOW_APGAR_1_CANDIDATE"] = (profiled["A_S_1"] < 7).astype("Int64")
    profiled.loc[profiled["A_S_1"].isna(), "LOW_APGAR_1_CANDIDATE"] = pd.NA
    profiled["LOW_APGAR_5_CANDIDATE"] = (profiled["A_S_5"] < 7).astype("Int64")
    profiled.loc[profiled["A_S_5"].isna(), "LOW_APGAR_5_CANDIDATE"] = pd.NA

    rows = []
    groups = [("Total", profiled), *[(LABOR_LABELS[g], profiled[profiled["LABOR_ONSET_GROUP_FINAL"].astype(str).eq(g)]) for g in LABOR_ORDER]]
    continuous = {
        "Birth weight": "BIRTH_WEIGHT",
        "Apgar score at 1 minute": "A_S_1",
        "Apgar score at 5 minutes": "A_S_5",
        "Stage 1 labor duration": "STAGE1_MINS",
        "Stage 2 labor duration": "STAGE2_MINS_CLEAN_FINAL",
    }
    binary = {
        "Operative delivery": "OPERATIVE_DELIVERY_BINARY_FINAL",
        "Low Apgar candidate at 1 minute": "LOW_APGAR_1_CANDIDATE",
        "Low Apgar candidate at 5 minutes": "LOW_APGAR_5_CANDIDATE",
    }
    for label, col in binary.items():
        row = {"Outcome": label, "Type": "Binary", "Missing n": int(profiled[col].isna().sum())}
        for group_label, subset in groups:
            valid = subset[col].dropna()
            row[group_label] = fmt_cat(int(valid.eq(1).sum()), len(valid))
        rows.append(row)
    for label, col in continuous.items():
        row = {"Outcome": label, "Type": "Continuous", "Missing n": int(profiled[col].isna().sum())}
        for group_label, subset in groups:
            row[group_label] = fmt_cont(subset[col])
        rows.append(row)
    return {
        "Table 4": pd.DataFrame(rows),
        "Footnotes": pd.DataFrame({"Footnote": ["Continuous outcomes are shown as mean ± SD; median [IQR]. Binary outcomes are shown as n (%)."]}),
    }


def raw_record_count() -> int:
    if not RAW_FILE.exists():
        return np.nan  # type: ignore[return-value]
    try:
        return int(len(pd.read_excel(RAW_FILE)))
    except Exception:
        return np.nan  # type: ignore[return-value]


def figure1(df: pd.DataFrame) -> None:
    raw_n = raw_record_count()
    strict_n = len(df)
    spontaneous_n = int(df["LABOR_ONSET_GROUP_FINAL"].astype(str).eq("spontaneous_labor").sum())
    induction_n = int(df["LABOR_ONSET_GROUP_FINAL"].astype(str).eq("non_spontaneous_or_induction").sum())
    review_n = int(df["FLAG_LABOR_ONSET_REQUIRES_REVIEW"].fillna(0).eq(1).sum())

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis("off")
    boxes = [
        (0.5, 0.88, f"Raw records from delivery dataset\nn = {raw_n if not pd.isna(raw_n) else 'NA'}"),
        (0.5, 0.66, f"Eligible records during strict COVID admission policy period\nn = {strict_n}"),
        (0.5, 0.44, f"Final analytic cohort\nn = {strict_n}\nReview-required labor onset cases retained for main analysis\nn = {review_n}"),
        (0.27, 0.18, f"Spontaneous labor\nn = {spontaneous_n}"),
        (0.73, 0.18, f"Non-spontaneous/induction\nn = {induction_n}"),
    ]
    for x, y, text in boxes:
        ax.text(x, y, text, ha="center", va="center", fontsize=10, bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="black"))
    arrow = dict(arrowstyle="->", color="black", lw=1)
    ax.annotate("", xy=(0.5, 0.72), xytext=(0.5, 0.82), arrowprops=arrow)
    ax.annotate("", xy=(0.5, 0.50), xytext=(0.5, 0.60), arrowprops=arrow)
    ax.annotate("", xy=(0.27, 0.25), xytext=(0.45, 0.38), arrowprops=arrow)
    ax.annotate("", xy=(0.73, 0.25), xytext=(0.55, 0.38), arrowprops=arrow)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "pub_figure1_study_flow.png", dpi=300)
    plt.close(fig)


def figure2(df: pd.DataFrame) -> None:
    counts = pd.crosstab(df["LABOR_ONSET_GROUP_FINAL"].astype(str), df["DELIVERY_MODE_GROUP_FINAL"].astype(str)).reindex(LABOR_ORDER)
    modes = [m for m in MODE_ORDER if m in counts.columns]
    pct = counts[modes].div(counts[modes].sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(7, 4.8))
    bottom = np.zeros(len(pct))
    for mode in modes:
        ax.bar([LABOR_LABELS[g] for g in pct.index], pct[mode], bottom=bottom, label=mode)
        bottom += pct[mode].values
    ax.set_ylabel("Percentage")
    ax.set_ylim(0, 100)
    ax.set_title("Mode of birth by labor onset pathway")
    ax.legend(title="Mode of birth")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "pub_figure2_mode_of_birth_by_labor_onset.png", dpi=300)
    plt.close(fig)


def figure3(df: pd.DataFrame) -> None:
    rows = []
    for group in LABOR_ORDER:
        subset = df[df["LABOR_ONSET_GROUP_FINAL"].astype(str).eq(group)]
        n = len(subset)
        events = int(subset["CS_BINARY_FINAL"].sum())
        rows.append({"group": group, "rate": events / n * 100 if n else np.nan, "events": events, "n": n})
    plot = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bars = ax.bar([LABOR_LABELS[g] for g in plot["group"]], plot["rate"], color=["#4C78A8", "#F58518"])
    ax.set_ylabel("Cesarean delivery rate (%)")
    ax.set_title("Cesarean delivery rate by labor onset pathway")
    for bar, row in zip(bars, plot.itertuples(index=False)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1, f"{row.rate:.1f}%\n{row.events}/{row.n}", ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(plot["rate"].max() * 1.35, 15))
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "pub_figure3_cesarean_rate_by_labor_onset.png", dpi=300)
    plt.close(fig)


def figure4(table2_estimates: pd.DataFrame) -> None:
    term = "labor_non_spontaneous_induction"
    plot = table2_estimates[table2_estimates["Term"].eq(term)].copy()
    plot = plot.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    y = np.arange(len(plot))
    ax.errorbar(
        plot["OR"],
        y,
        xerr=[plot["OR"] - plot["95% CI lower"], plot["95% CI upper"] - plot["OR"]],
        fmt="o",
        color="black",
        ecolor="black",
        capsize=3,
    )
    ax.axvline(1, color="gray", linestyle="--", lw=1)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(plot["Model"])
    ax.set_xlabel("Odds ratio (log scale)")
    ax.set_title("Cesarean delivery: non-spontaneous/induction vs spontaneous labor")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "pub_figure4_forest_plot_cs_model.png", dpi=300)
    plt.close(fig)


def create_figures(df: pd.DataFrame, table2_estimates: pd.DataFrame) -> None:
    figure1(df)
    figure2(df)
    figure3(df)
    figure4(table2_estimates)


def manuscript_values(df: pd.DataFrame, t2: pd.DataFrame, t3: pd.DataFrame) -> dict[str, Any]:
    spont = df[df["LABOR_ONSET_GROUP_FINAL"].astype(str).eq("spontaneous_labor")]
    induction = df[df["LABOR_ONSET_GROUP_FINAL"].astype(str).eq("non_spontaneous_or_induction")]
    primary = t2[t2["Term"].eq("labor_non_spontaneous_induction")].copy()
    adjusted = primary[primary["Model"].str.contains("Model 2")].iloc[0]
    multinom_labor = t3[t3["Term"].eq("labor_non_spontaneous_induction")].copy()
    return {
        "n": len(df),
        "spont_n": len(spont),
        "induction_n": len(induction),
        "spont_cs": spont["CS_BINARY_FINAL"].mean() * 100,
        "induction_cs": induction["CS_BINARY_FINAL"].mean() * 100,
        "adjusted_or": adjusted["OR"],
        "adjusted_low": adjusted["95% CI lower"],
        "adjusted_high": adjusted["95% CI upper"],
        "adjusted_p": adjusted["p-value"],
        "ved_rate_spont": spont["DELIVERY_MODE_GROUP_FINAL"].astype(str).eq("VED").mean() * 100,
        "ved_rate_induction": induction["DELIVERY_MODE_GROUP_FINAL"].astype(str).eq("VED").mean() * 100,
        "nsd_rate_spont": spont["DELIVERY_MODE_GROUP_FINAL"].astype(str).eq("NSD").mean() * 100,
        "nsd_rate_induction": induction["DELIVERY_MODE_GROUP_FINAL"].astype(str).eq("NSD").mean() * 100,
        "review_n": int(df["FLAG_LABOR_ONSET_REQUIRES_REVIEW"].fillna(0).eq(1).sum()),
        "t3_labor": multinom_labor,
    }


def write_results_summary(df: pd.DataFrame, t2: pd.DataFrame, t3: pd.DataFrame) -> None:
    v = manuscript_values(df, t2, t3)
    ved_row = v["t3_labor"][v["t3_labor"]["Outcome contrast"].eq("VED vs NSD")].iloc[0]
    cs_row = v["t3_labor"][v["t3_labor"]["Outcome contrast"].eq("CS vs NSD")].iloc[0]
    text = f"""# Results Summary for Manuscript

## Participant Characteristics

The final analytic cohort included {v['n']} births during the strict COVID admission policy period, which was treated as the study context. Labor onset was classified as spontaneous labor in {v['spont_n']} births and non-spontaneous/induction in {v['induction_n']} births. Review-required mixed labor onset records were retained in the main analysis and flagged for sensitivity analysis (n = {v['review_n']}).

## Mode of Birth Distribution

Mode of birth differed by labor onset pathway. Cesarean delivery occurred in {v['spont_cs']:.1f}% of spontaneous labor births and {v['induction_cs']:.1f}% of non-spontaneous/induction births. VED accounted for {v['ved_rate_spont']:.1f}% and {v['ved_rate_induction']:.1f}% of births, respectively, while NSD accounted for {v['nsd_rate_spont']:.1f}% and {v['nsd_rate_induction']:.1f}%.

## Cesarean Delivery Results

In adjusted logistic regression, non-spontaneous/induction labor onset was associated with higher odds of cesarean delivery compared with spontaneous labor (OR {v['adjusted_or']:.2f}, 95% CI {v['adjusted_low']:.2f} to {v['adjusted_high']:.2f}, {fmt_p_sentence(v['adjusted_p'])}). The model adjusted for maternal age, BMI, gestational age, birth weight, gravida, and para.

## Multinomial Regression Results

Using NSD as the reference outcome, non-spontaneous/induction labor onset was associated with VED versus NSD (RRR {ved_row['RRR']:.2f}, 95% CI {ved_row['95% CI lower']:.2f} to {ved_row['95% CI upper']:.2f}, {fmt_p_sentence(ved_row['p-value'])}) and CS versus NSD (RRR {cs_row['RRR']:.2f}, 95% CI {cs_row['95% CI lower']:.2f} to {cs_row['95% CI upper']:.2f}, {fmt_p_sentence(cs_row['p-value'])}). VBAC was not modeled separately because no VBAC cases were observed.

## Secondary Outcomes

Secondary outcomes, including operative delivery, birth weight, Apgar scores, low Apgar candidates, and labor duration, are summarized descriptively by labor onset pathway. These outcomes should be interpreted as descriptive associations and not as causal effects.

## Sensitivity Analysis

The adjusted sensitivity model excluding review-required mixed labor onset records remained directionally consistent with the main adjusted model. This supports the robustness of the primary labor onset contrast while preserving the main analysis approach in which flagged records were retained.
"""
    (DOCS_DIR / "results_summary_for_manuscript.md").write_text(text, encoding="utf-8")


def write_methods_skeleton() -> None:
    text = """# Methods Skeleton for Manuscript

## Study Design and Setting

This retrospective observational study examined births occurring during the strict COVID admission policy period at the study institution. The strict admission policy period is described as the clinical and operational study context and was not treated as the exposure of interest.

## Participants

Eligible records were births in the processed delivery dataset with delivery dates during the strict COVID admission policy period and available final labor onset and mode-of-birth classifications. The final analytic cohort retained records flagged as requiring labor onset review for the main analysis, with sensitivity analysis excluding these records.

## Exposure: Labor Onset Pathway

The exposure was labor onset pathway, classified using the final PGADM definition. Spontaneous labor was defined by PGADM values indicating labor signs, including labor pain, rupture of membranes, or bloody show. Non-spontaneous/induction was defined by PGADM values indicating induction or non-spontaneous admission. Records containing both induction and labor-sign terms were retained and flagged for sensitivity analysis.

## Outcomes

The primary outcome was cesarean delivery. Secondary outcomes included operative delivery, mode of birth, birth weight, Apgar score at 1 minute, Apgar score at 5 minutes, low Apgar candidate indicators, and stage 1 and stage 2 labor durations.

## Covariates

Covariates selected for adjusted models were maternal age, BMI, gestational age in weeks, birth weight, gravida, and para.

## Statistical Analysis

Participant characteristics were summarized by labor onset pathway. Continuous variables were reported as mean ± SD and median [IQR]. Categorical variables were reported as n (%). Logistic regression was used to estimate the association between labor onset pathway and cesarean delivery. Multivariable models adjusted for maternal age, BMI, gestational age, birth weight, gravida, and para. Mode of birth was evaluated using modeled contrasts for VED versus NSD and CS versus NSD, with NSD as the reference outcome.

## Sensitivity Analysis

A sensitivity logistic regression model repeated the adjusted cesarean delivery analysis after excluding records with mixed or review-required labor onset classification.

## Reproducibility and Data Processing

Raw data were not modified. Analysis variables were derived from the v03 processed dataset. Publication-ready tables and figures were generated using a scripted workflow, and generated outputs were saved as Excel tables and PNG figures.
"""
    (DOCS_DIR / "methods_skeleton_for_manuscript.md").write_text(text, encoding="utf-8")


def write_tables_figures_index() -> None:
    text = """# Tables and Figures Index

| Item | Title | Manuscript section |
| --- | --- | --- |
| Table 1 | Participant characteristics by labor onset pathway | Results: Participant characteristics |
| Table 2 | Logistic regression for cesarean delivery | Results: Cesarean delivery |
| Table 3 | Mode of birth regression contrasts with NSD as reference | Results: Mode of birth |
| Table 4 | Secondary outcome profile by labor onset pathway | Results: Secondary outcomes |
| Figure 1 | Study flow diagram | Methods: Participants; Results: Cohort derivation |
| Figure 2 | Mode of birth by labor onset pathway | Results: Mode of birth |
| Figure 3 | Cesarean delivery rate by labor onset pathway | Results: Cesarean delivery |
| Figure 4 | Forest plot of cesarean delivery logistic regression models | Results: Cesarean delivery; Sensitivity analysis |
"""
    (DOCS_DIR / "tables_figures_index.md").write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    source = read_v03()
    df = make_analysis_df(source)

    t1 = table1(df)
    write_excel(OUTPUT_DIR / "pub_table1_participant_characteristics.xlsx", t1)

    t2 = table2(df)
    write_excel(OUTPUT_DIR / "pub_table2_cesarean_logistic_regression.xlsx", t2)

    t3 = table3(df)
    write_excel(OUTPUT_DIR / "pub_table3_multinomial_mode_of_birth.xlsx", t3)

    t4 = secondary_outcomes_table(df)
    write_excel(OUTPUT_DIR / "pub_table4_secondary_outcomes.xlsx", t4)

    create_figures(df, t2["Estimates"])
    write_results_summary(df, t2["Estimates"], t3["Estimates"])
    write_methods_skeleton()
    write_tables_figures_index()

    primary = t2["Estimates"][t2["Estimates"]["Term"].eq("labor_non_spontaneous_induction")]
    print("Created publication-ready tables, figures, and manuscript skeleton documents.")
    print(primary[["Model", "OR", "95% CI lower", "95% CI upper", "p-value", "Model N", "Event N", "Convergence status"]].to_string(index=False))


if __name__ == "__main__":
    main()
