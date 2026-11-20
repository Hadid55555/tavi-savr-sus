---
title: "Study protocol and statistical analysis plan — Transcatheter aortic valve implantation in Brazil's public and private health sectors, 2015–2025"
---

*English translation of the analysis plan frozen on 31 October 2026 (original in Portuguese: `tavi_savr/PLANO_ANALISE_v1.md`), with dated amendments. Prepared 16 November 2026.*

# 1. Objectives

**Primary:** to describe how the use of transcatheter aortic valve implantation (TAVI) and surgical aortic valve replacement (SAVR) evolved in Brazil and what differences in use exist between the Unified Health System (SUS) and private health plans, by age.

**Secondary:** age distribution of TAVI over time (shift towards younger patients?); age of SAVR patients over time; geography and centres; in-hospital mortality (descriptive only); SUS TAVI in patients younger than 75 years.

**Language:** results describe "differences in use associated with payer"; "inequity" is used only in the Discussion, qualified.

# 2. Design and data sources

Nationwide, population-based, repeated cross-sectional study of hospitalizations, reported according to STROBE/RECORD. Unit: one hospitalization.

| Source | Main period | Use |
|---|---|---|
| SIH/SUS reduced hospitalization records (RD) | 2008–2025 (2026 supplementary) | SUS TAVI and SAVR; age, sex, diagnoses, hospital, residence, in-hospital death |
| SIH/SUS professional services (SP) | 2008–2025 | SAVR within multiple-surgery hospitalizations |
| ANS TISS hospital open data | 2015–2025 (TAVI 2021–2025) | Private plans: 10-year age band, sex, municipality, death |
| CIHA (non-SUS hospitalization reports) | 2011–2025 | Self-pay, descriptive and supplementary only |
| IBGE population projection (rev. 2018) and ANS beneficiaries | 2008–2025 | Denominators |
| CNES | current | Hospitals, accreditation |

Reference year: year of admission (TISS: year of the event).

# 3. Definitions

- **TAVI:** SUS procedure codes 04.06.01.152-4 and 04.06.03.016-2; private plans TUSS 30912296.
- **Aortic SAVR (main):** SUS 04.06.01.069-2 with principal diagnosis I35, I06, Q23.0 or Q23.1, plus multiple-surgery hospitalizations (04.15.01.001-2, 04.15.02.003-4) with procedure 04.06.01.069-2 in the SP records and an aortic diagnosis; private plans TUSS 30902053 without TAVI, combined CABG–valve or multivalve codes, with the aortic valve in three bounds (lower: aortic diagnosis recorded; central: imputation by the known aortic fraction by year and age group; upper: all without a valve diagnosis). SUS sensitivity: include multiple-surgery hospitalizations with diagnosis I71 (valve plus aorta).
- **Combined procedures** (valve replacement plus CABG; multivalve) analysed separately.
- Age groups: <60, 60–69, 70–79, ≥80 years; SUS also in 5-year groups (75-year threshold).

# 4. Outcomes and analyses

1. Counts and rates per million by year × age group × payer, with three denominators (total population; beneficiaries; population without a plan = total − beneficiaries), directly standardized to the 2022 Brazilian population at ≥60 years, with 95% confidence intervals (gamma method; delta method for rate ratios).
2. TAVI as a percentage of TAVI + aortic SAVR, by age group and payer (three bounds in plans).
3. Annual age distribution of TAVI (proportions, distinct from rates).
4. SUS SAVR 2008–2025: age (median), stratified by degenerative (I35), rheumatic (I06) and congenital (Q23) diagnoses and isolated vs combined.
5. Geography: rates by state of residence (2025, ≥60, standardized), percentage treated outside the state of residence, distance from residence to hospital, hospitals with SAVR and without TAVI.
6. In-hospital mortality: descriptive by payer × age group. No comparison of quality between systems.
7. No causal interrupted time series: implementation described (SUS May 2024; TUSS April 2021).

# 5. Mandatory sensitivity analyses

Continuously reporting plans (2021–2025); June vs December beneficiaries; valve bounds; exclusion of states with very low TISS procedure coding (CE, AP, RO); exclusion of TAVI <75 years; SAVR including I71; 2026 (partial) excluded from main analyses.

# 6. Amendments (dated)

- **31 Oct 2026** (after first external review): numerator audit; 95% CIs and sensitivity of the payer ratio; monthly series (no modelling of the last months, affected by reporting lag); between-state inequality (Gini, Theil); implementation of the 25 accredited hospitals; distance to the nearest active SUS TAVI centre (≥10 procedures in 2024–2025); SUS TAVI <75 years by hospital and period.
- **31 Oct 2026:** prosthesis type (biological vs mechanical) moved to a separate study; only lesion type of TAVI kept here.
- **3 Nov 2026** (after second external review): in-hospital mortality kept descriptive only — the planned SUS multilevel logistic model was not fitted, because neither data source contains surgical risk or frailty; SAVR age reported as medians (quantile regression not performed).
- **5 Nov 2026** (after third external review): burden indicators independent of insurance (SIM deaths with I35 as underlying cause; AVR per death by state); CNES cardiovascular accreditations by state; descriptive state-level negative binomial model (offset: expected count by indirect standardization; covariates: plan coverage, active SUS centre, I35 death rate; Poisson with robust errors as sensitivity); decomposition of the crude payer difference by age structure; e-NatJus judicial technical notes for I35/I06 (2020–2026; aggregated variables only).
- **5 Nov 2026** (internal review): payer ratio by tertile of state plan coverage (overlap of denominators).
- **13 Nov 2026:** age-standardized aortic stenosis mortality with the definition of Siddiqi et al. 2026 (I35.0, I35.2, I06.0, I06.2 as underlying or contributing cause; ≥45 years; 2000 US standard population), average annual percent change by log-linear regression.
- **14 Nov 2026:** hospital location approximated by the centroid of the hospital's municipality (as residence), for the public data package without establishment coordinates; the CIHA (self-pay) was not used in the main analyses.

# 7. Ethics and data

Public, anonymized data; under National Health Council Resolution 510/2016 no ethics approval was required. Code, pseudonymized analytic data and results: https://github.com/Hadid55555/tavi-savr-sus.
