from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_FILE = PROJECT_ROOT / "data" / "processed" / "delivery_mode_analysis_variables_v02.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

BASE_COVARIATES = [
    "LABOR_ONSET_GROUP",
    "Age",
    "BMI",
    "GESTAT_WEEKS_DECIMAL",
    "BIRTH_WEIGHT",
    "GRAVIDA",
    "PARA",
]

EXPLORATORY_COVARIATES = BASE_COVARIATES + ["STAGE1_MINS", "STAGE2_MINS_CLEAN"]


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


def build_modeling_dataset(df: pd.DataFrame) -> pd.DataFrame:
    model_df = df.copy()
    model_df["CS_BINARY"] = model_df["DELIVERY_MODE_GROUP"].eq("CS").astype("int64")
    model_df["OPERATIVE_DELIVERY_BINARY"] = model_df["DELIVERY_MODE_GROUP"].isin(["CS", "VED"]).astype("int64")
    model_df["LABOR_ONSET_GROUP"] = pd.Categorical(
        model_df["LABOR_ONSET_GROUP"],
        categories=["spontaneous_labor", "non_spontaneous_or_induction"],
    )
    model_df["DELIVER_MODE_GROUP"] = pd.Categorical(
        model_df["DELIVERY_MODE_GROUP"],
        categories=["NSD", "VED", "CS"],
    )
    for col in [
        "Age",
        "BMI",
        "GESTAT_WEEKS_DECIMAL",
        "BIRTH_WEIGHT",
        "GRAVIDA",
        "PARA",
        "STAGE1_MINS",
        "STAGE2_MINS_CLEAN",
        "FLAG_STAGE1_EXTREME",
        "FLAG_STAGE2_EXTREME",
        "FLAG_LABOR_ONSET_REQUIRES_REVIEW",
    ]:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")
    return model_df


def crosstab_with_pct(df: pd.DataFrame, row: str, col: str) -> pd.DataFrame:
    counts = pd.crosstab(df[row], df[col], dropna=False)
    pct = pd.crosstab(df[row], df[col], normalize="index", dropna=False)
    rows = []
    for row_value in counts.index:
        for col_value in counts.columns:
            rows.append(
                {
                    row: row_value,
                    col: col_value,
                    "count": int(counts.loc[row_value, col_value]),
                    "row_pct": float(pct.loc[row_value, col_value]),
                }
            )
    return pd.DataFrame(rows)


def crude_or_2x2(df: pd.DataFrame, outcome: str, exposed_value: str = "non_spontaneous_or_induction") -> pd.DataFrame:
    data = df[["LABOR_ONSET_GROUP", outcome]].dropna()
    exposed = data["LABOR_ONSET_GROUP"].astype(str).eq(exposed_value)
    event = data[outcome].eq(1)
    a = int((exposed & event).sum())
    b = int((exposed & ~event).sum())
    c = int((~exposed & event).sum())
    d = int((~exposed & ~event).sum())

    correction = 0.5 if min(a, b, c, d) == 0 else 0
    aa, bb, cc, dd = a + correction, b + correction, c + correction, d + correction
    log_or = np.log((aa * dd) / (bb * cc))
    se = np.sqrt(1 / aa + 1 / bb + 1 / cc + 1 / dd)
    return pd.DataFrame(
        [
            {
                "outcome": outcome,
                "exposure_contrast": f"{exposed_value} vs spontaneous_labor",
                "event_exposed": a,
                "non_event_exposed": b,
                "event_reference": c,
                "non_event_reference": d,
                "OR": np.exp(log_or),
                "CI_95_low": np.exp(log_or - 1.96 * se),
                "CI_95_high": np.exp(log_or + 1.96 * se),
                "continuity_correction_used": correction,
            }
        ]
    )


def crude_association_report(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "labor_onset_by_cs": crosstab_with_pct(df, "LABOR_ONSET_GROUP", "CS_BINARY"),
        "labor_onset_by_operative": crosstab_with_pct(df, "LABOR_ONSET_GROUP", "OPERATIVE_DELIVERY_BINARY"),
        "labor_onset_by_delivery_mode": crosstab_with_pct(df, "LABOR_ONSET_GROUP", "DELIVER_MODE_GROUP"),
        "crude_or_cs": crude_or_2x2(df, "CS_BINARY"),
        "crude_or_operative": crude_or_2x2(df, "OPERATIVE_DELIVERY_BINARY"),
    }


def design_matrix(df: pd.DataFrame, predictors: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = predictors.copy()
    data = df[cols].copy()
    data = data.dropna()
    x = pd.DataFrame(index=data.index)
    if "LABOR_ONSET_GROUP" in predictors:
        x["LABOR_ONSET_non_spontaneous_or_induction"] = (
            data["LABOR_ONSET_GROUP"].astype(str).eq("non_spontaneous_or_induction").astype("int64")
        )
    for col in predictors:
        if col == "LABOR_ONSET_GROUP":
            continue
        x[col] = pd.to_numeric(data[col], errors="coerce")
    x = sm.add_constant(x, has_constant="add")
    return data, x


def fit_logistic(df: pd.DataFrame, outcome: str, predictors: list[str], model_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    needed = [outcome, *predictors]
    model_data = df[needed].dropna().copy()
    if model_data[outcome].nunique() < 2:
        diagnostics = pd.DataFrame(
            [
                {
                    "model": model_name,
                    "outcome": outcome,
                    "model_N": len(model_data),
                    "event_N": int(model_data[outcome].sum()) if len(model_data) else 0,
                    "converged": False,
                    "status": "not_fit",
                    "message": "Outcome has fewer than two levels after complete-case filtering.",
                }
            ]
        )
        return pd.DataFrame(), diagnostics

    _, x = design_matrix(model_data, predictors)
    y = model_data[outcome].astype(float)
    try:
        fitted = sm.Logit(y, x).fit(disp=False, maxiter=200)
        params = fitted.params
        conf = fitted.conf_int()
        pvalues = fitted.pvalues
        result = pd.DataFrame(
            {
                "model": model_name,
                "outcome": outcome,
                "term": params.index,
                "coefficient": params.values,
                "OR": np.exp(params.values),
                "CI_95_low": np.exp(conf[0].values),
                "CI_95_high": np.exp(conf[1].values),
                "p_value": pvalues.values,
                "model_N": int(fitted.nobs),
                "event_N": int(y.sum()),
                "convergence_status": bool(fitted.mle_retvals.get("converged", False)),
            }
        )
        diagnostics = pd.DataFrame(
            [
                {
                    "model": model_name,
                    "outcome": outcome,
                    "model_N": int(fitted.nobs),
                    "event_N": int(y.sum()),
                    "converged": bool(fitted.mle_retvals.get("converged", False)),
                    "status": "fit",
                    "message": "",
                }
            ]
        )
        return result, diagnostics
    except Exception as exc:
        diagnostics = pd.DataFrame(
            [
                {
                    "model": model_name,
                    "outcome": outcome,
                    "model_N": len(model_data),
                    "event_N": int(y.sum()) if len(model_data) else 0,
                    "converged": False,
                    "status": "error",
                    "message": str(exc),
                }
            ]
        )
        return pd.DataFrame(), diagnostics


def logistic_models(df: pd.DataFrame, outcome: str, include_exploratory: bool = False) -> dict[str, pd.DataFrame]:
    specs = [
        ("Model 1 crude", ["LABOR_ONSET_GROUP"]),
        ("Model 2 adjusted", BASE_COVARIATES),
    ]
    if include_exploratory:
        specs.append(("Model 3 exploratory", EXPLORATORY_COVARIATES))

    results = []
    diagnostics = []
    for model_name, predictors in specs:
        result, diag = fit_logistic(df, outcome, predictors, model_name)
        if not result.empty:
            results.append(result)
        diagnostics.append(diag)

    return {
        "model_results": pd.concat(results, ignore_index=True) if results else pd.DataFrame(),
        "model_diagnostics": pd.concat(diagnostics, ignore_index=True),
    }


def multinomial_model(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    needed = ["DELIVER_MODE_GROUP", *BASE_COVARIATES]
    model_data = df[needed].dropna().copy()
    outcome_counts = model_data["DELIVER_MODE_GROUP"].value_counts()
    diagnostics_base = {
        "model": "Multinomial adjusted",
        "outcome": "DELIVER_MODE_GROUP",
        "model_N": len(model_data),
        "status": "not_fit",
        "message": "",
    }
    if len(outcome_counts) < 3 or (outcome_counts < 20).any():
        diagnostics_base["message"] = f"Insufficient category counts: {outcome_counts.to_dict()}"
        return {"model_results": pd.DataFrame(), "model_diagnostics": pd.DataFrame([diagnostics_base])}

    y = pd.Categorical(model_data["DELIVER_MODE_GROUP"], categories=["NSD", "VED", "CS"])
    y_codes = pd.Series(y.codes, index=model_data.index)
    _, x = design_matrix(model_data, BASE_COVARIATES)
    try:
        fitted = sm.MNLogit(y_codes, x).fit(disp=False, maxiter=300)
        params = fitted.params
        conf = fitted.conf_int()
        pvalues = fitted.pvalues
        rows = []
        category_map = {0: "VED_vs_NSD", 1: "CS_vs_NSD"}
        for outcome_code in params.columns:
            for term in params.index:
                coef = params.loc[term, outcome_code]
                # statsmodels labels MNLogit confidence intervals by the modeled
                # non-reference outcome code (1, 2) while params columns are 0, 1.
                conf_key = (str(int(outcome_code) + 1), term)
                ci_low = conf.loc[conf_key, "lower"]
                ci_high = conf.loc[conf_key, "upper"]
                rows.append(
                    {
                        "model": "Multinomial adjusted",
                        "outcome_contrast": category_map.get(int(outcome_code), str(outcome_code)),
                        "reference_category": "NSD",
                        "term": term,
                        "coefficient": coef,
                        "RRR": np.exp(coef),
                        "CI_95_low": np.exp(ci_low),
                        "CI_95_high": np.exp(ci_high),
                        "p_value": pvalues.loc[term, outcome_code],
                        "model_N": int(fitted.nobs),
                        "convergence_status": bool(fitted.mle_retvals.get("converged", False)),
                    }
                )
        diagnostics_base.update(
            {
                "status": "fit",
                "message": "",
                "converged": bool(fitted.mle_retvals.get("converged", False)),
                "category_counts": str(outcome_counts.to_dict()),
            }
        )
        return {"model_results": pd.DataFrame(rows), "model_diagnostics": pd.DataFrame([diagnostics_base])}
    except Exception as exc:
        diagnostics_base["status"] = "error"
        diagnostics_base["message"] = str(exc)
        diagnostics_base["category_counts"] = str(outcome_counts.to_dict())
        return {"model_results": pd.DataFrame(), "model_diagnostics": pd.DataFrame([diagnostics_base])}


def sensitivity_excluding_review(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sensitivity = df[df["FLAG_LABOR_ONSET_REQUIRES_REVIEW"].eq(0)].copy()
    result, diag = fit_logistic(
        sensitivity,
        "CS_BINARY",
        BASE_COVARIATES,
        "CS_BINARY Model 2 excluding labor-onset review-required records",
    )
    excluded = pd.DataFrame(
        [
            {
                "exclusion_rule": "FLAG_LABOR_ONSET_REQUIRES_REVIEW == 1",
                "excluded_n": int(df["FLAG_LABOR_ONSET_REQUIRES_REVIEW"].sum()),
                "remaining_n": len(sensitivity),
            }
        ]
    )
    return {"model_results": result, "model_diagnostics": diag, "exclusion_summary": excluded}


def main() -> None:
    ensure_dirs()
    df = build_modeling_dataset(read_analysis_data())

    write_excel(OUTPUT_DIR / "33_crude_association_labor_onset_delivery_mode.xlsx", crude_association_report(df))
    write_excel(OUTPUT_DIR / "34_logistic_model_cs_binary.xlsx", logistic_models(df, "CS_BINARY", include_exploratory=True))
    write_excel(
        OUTPUT_DIR / "35_logistic_model_operative_delivery.xlsx",
        logistic_models(df, "OPERATIVE_DELIVERY_BINARY", include_exploratory=False),
    )
    write_excel(OUTPUT_DIR / "36_multinomial_delivery_mode_model.xlsx", multinomial_model(df))
    write_excel(OUTPUT_DIR / "37_sensitivity_excluding_mixed_labor_onset.xlsx", sensitivity_excluding_review(df))

    crude_cs = crude_or_2x2(df, "CS_BINARY")
    print("Preliminary delivery mode modeling skeleton completed.")
    print(f"Rows assessed: {len(df)}")
    print(f"Crude CS OR: {crude_cs.loc[0, 'OR']:.3f}")
    print(f"Outputs written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
