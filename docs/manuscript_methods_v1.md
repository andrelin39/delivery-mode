# Manuscript Methods v1

## 2.1 Study design and setting

This retrospective observational study examined the association between labor onset pathway and mode of birth among women giving birth during the strict COVID-19 admission policy period at the study institution. The strict COVID-19 admission policy period was used to define the clinical and operational study context. It was not treated as the exposure of interest, and COVID-19 policy was not evaluated as an explanatory exposure for birth outcomes.

## 2.2 Participants

The study population was derived from the institutional delivery dataset. Eligible records were births with delivery dates within the strict COVID-19 admission policy period and with available final classifications for labor onset pathway and mode of birth. Records with mixed or review-required labor onset information were retained in the main analytic cohort and were identified using a prespecified sensitivity flag. The final analytic cohort included 1,364 births, with 681 classified as spontaneous labor and 683 classified as non-spontaneous labor or induction.

## 2.3 Labor onset pathway classification

The exposure was labor onset pathway. Labor onset was classified using the final PGADM definition. Spontaneous labor was defined when PGADM indicated labor signs, including labor pain, rupture of membranes, or bloody show. Non-spontaneous labor or induction was defined when PGADM indicated induction or non-spontaneous admission. Records that contained both induction terms and labor-sign terms were classified as non-spontaneous labor or induction in the main analysis and were flagged as requiring review for sensitivity analysis.

## 2.4 Outcome measures

The primary outcome was cesarean delivery, defined as cesarean section versus all non-cesarean births. Secondary outcomes included operative delivery, mode of birth, birth weight, Apgar score at 1 minute, Apgar score at 5 minutes, low Apgar candidate indicators, and stage 1 and stage 2 labor durations. Mode of birth was categorized as normal spontaneous delivery, vacuum extraction delivery, cesarean section, or vaginal birth after cesarean when present. Operative delivery was defined as cesarean section or vacuum extraction delivery. Low Apgar candidates were defined as Apgar score less than 7 at 1 minute and less than 7 at 5 minutes.

## 2.5 Covariates

Covariates were selected before model fitting based on clinical relevance and availability in the processed dataset. Adjusted models included maternal age, body mass index, gestational age in weeks, birth weight, gravida, and para.

## 2.6 Statistical analysis

Participant characteristics were summarized by labor onset pathway. Continuous variables were reported as mean plus or minus standard deviation and median with interquartile range. Categorical variables were reported as number and percentage. Logistic regression was used to estimate the association between labor onset pathway and cesarean delivery. The unadjusted model included labor onset pathway only. The adjusted model included labor onset pathway, maternal age, body mass index, gestational age, birth weight, gravida, and para. Odds ratios, 95% confidence intervals, p values, model sample size, event count, and convergence status were reported. Spontaneous labor was used as the reference category.

Mode of birth was evaluated using multinomial logistic regression, with normal spontaneous delivery as the reference outcome. The modeled outcome contrasts were vacuum extraction delivery versus normal spontaneous delivery and cesarean section versus normal spontaneous delivery. The multinomial model included labor onset pathway and the same covariates as the adjusted cesarean delivery model. Relative risk ratios, 95% confidence intervals, p values, model sample size, and convergence status were reported. Vaginal birth after cesarean was retained in the data dictionary but was not modeled separately because no vaginal birth after cesarean cases were observed.

All analyses were conducted using the v03 processed analysis dataset. Raw data were not modified. Publication-ready tables were exported as Excel files, and figures were exported as PNG files.

## 2.7 Sensitivity analysis

A prespecified sensitivity analysis repeated the adjusted logistic regression for cesarean delivery after excluding records flagged as requiring review for labor onset classification. This sensitivity analysis evaluated whether the primary association between labor onset pathway and cesarean delivery was materially changed after removal of mixed or review-required labor onset records.
