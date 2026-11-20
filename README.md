# Code and data for: Transcatheter aortic valve implantation in Brazil — a nationwide study of public and private health-sector hospitalizations, 2015–2025

This repository contains the code, the pseudonymized analytic data and the aggregated results needed to reproduce the
tables, figures and supplementary tables of the manuscript *"Transcatheter aortic valve implantation in Brazil: a
nationwide study of public and private health-sector hospitalizations, 2015–2025"* (Hadid L, Salek L, Passos FS, Caldonazo T; manuscript in
preparation).

The study describes how transcatheter aortic valve implantation (TAVI) was incorporated in Brazil's Unified Health
System (SUS) and in private health plans: volume and age-standardized rates by payer, age distribution, geography and
centre implementation, aortic-stenosis mortality, judicial requests for TAVI, and comparison with other countries.

Folder and file names are in Portuguese, as in the original project; this README is the guide.

## Data sources (all public)

| Source | Content used | Period |
|---|---|---|
| SIH/SUS RD (reduced hospitalization records), DATASUS, via the public mirror healthbr-data (`https://data.sidneybissoli.com/sih/`) | SUS-reimbursed hospitalizations for TAVI, aortic valve replacement and related procedures | Jan 2008–Aug 2026 |
| SIH/SUS SP (professional services) | procedures billed inside multiple-surgery hospitalizations | Jan 2008–Aug 2026 |
| ANS TISS hospital open data (`https://dadosabertos.ans.gov.br/FTP/PDA/TISS/HOSPITALAR/`) | private-plan hospitalizations with TUSS valve codes | 2015–2025 |
| SIM (Mortality Information System), DATASUS (public compilation on Kaggle, `rafatrindade/brazilian-kaggle-datahub`) | deaths with I35/I06 in any field of the death certificate | 2008–2025 |
| CNES accreditation file, DATASUS (same compilation) | hospitals with cardiovascular accreditation (08.01, 08.02, 08.03, 08.15) | Sep 2026 |
| IBGE population projection, revision 2018 (SIDRA table 7358) | denominators by state, year and age | 2008–2025 |
| ANS beneficiaries by state and age (December; June for sensitivity) | denominators for private plans | 2015–2025 |
| CNJ e-NatJus public technical notes | judicial requests for TAVI (aggregated variables only, no names) | 2020–Oct 2026 |
| Municipal coordinates (kelvins/municipios-brasileiros) and state boundaries (click_that_hood) | geography | — |

## Repository layout

```
reproduce.sh                       runs every analysis in order
docs/study_protocol.md             study protocol and analysis plan (with dated amendments)
requirements.txt                   exact package versions
tools/build_package_data.py        how the pseudonymized data in saida_tavi/ were built from the raw extracts
saida_tavi/                        analytic data (pseudonymized, gzip CSV)
  parciais/RD_valvas_2008_2026.csv.gz          SIH/SUS RD, selected hospitalizations (one row per AIH record)
  sp/parciais/SP_multiplas_2008_2026.csv.gz    SIH/SUS SP rows of multiple-surgery hospitalizations (6 columns)
  tiss/parciais/tiss_valvas_2015_2025.csv.gz   ANS TISS hospitalizations with valve codes or aortic diagnoses
  tiss/parciais/_cobertura.jsonl               coverage of the 3,564 TISS state-month files
  tiss_planos/parciais/tiss_internacoes_plano_uf_ano.csv.gz   all TISS hospitalizations counted by plan, state, year
  sim_valva_aortica_obitos.csv.gz              SIM deaths with I35/I06 in any field
  kaggle_raw/cnes_habilitacoes.parquet         CNES cardiovascular accreditations
artigo/dados_ref/, ciha/dados_ref/, novas_pesquisas/   population, beneficiaries and SIGTAP reference files
tavi_savr/                         analysis and extraction scripts
  dados_ref/                       hospital reference (pseudonymized), coordinates, state map, e-NatJus extract
  resultados_*/                    aggregated results (CSV) produced by the scripts
  manuscrito/                      Table 1, international table (Table 2) and figure scripts; figuras/ = Figures 1–4
```

## Study protocol

The study protocol and statistical analysis plan (frozen 31 October 2026, with dated amendments) is in
[`docs/study_protocol.md`](docs/study_protocol.md).

## How to reproduce

```
pip install -r requirements.txt
bash reproduce.sh
```

`reproduce.sh` runs, from the repository root (about 20–40 minutes on a laptop):

| Order | Script | Output |
|---|---|---|
| 1 | `tavi_savr/contagens_fase1.py` | `resultados_fase1/`: counts by group and year; SUS SAVR age (Supplementary Table S12) |
| 2 | `tavi_savr/taxas_75mais.py` | rates per million ≥75 years (phase 1) |
| 3 | `tavi_savr/nacional_sus_ans.py` | `resultados_nacional/`: events by source × group × year × age; denominators; rates; age distribution; in-hospital mortality |
| 4 | `tavi_savr/auditorias.py` | `resultados_auditoria/` A1–A4: multiple surgeries, standardized rates and valve bounds, TAVI <75 years |
| 5 | `tavi_savr/tiss_completude_analise.py` | `resultados_auditoria/` T1–T4: TISS completeness (continuously reporting plans, coding by state) |
| 6 | `tavi_savr/geografia.py` | `resultados_geografia/`: rates by state of residence, travel, hospitals by state, map |
| 7 | `tavi_savr/analises_v2.py` | `resultados_v2/` R1–R7: numerator audit, 95% CIs, monthly series, Gini/Theil, implementation of accredited hospitals, distance to nearest active centre, TAVI <75 |
| 8 | `tavi_savr/sensibilidade_razao.py` | `resultados_v2/R2b`: payer ratio by tertile of plan coverage |
| 9 | `tavi_savr/carga_capacidade.py` | `resultados_carga_capacidade/`: I35 deaths, AVR per death by state, CNES accreditations |
| 10 | `tavi_savr/sim_mortalidade_padronizada.py` | age-standardized aortic-stenosis mortality (2000 US standard), trends |
| 11 | `tavi_savr/modelo_uf.py` | `resultados_modelo_uf/`: state-level negative binomial model, decomposition |
| 12 | `tavi_savr/natjus_analise.py` | `resultados_judicializacao/`: e-NatJus judicial requests |
| 13 | `tavi_savr/manuscrito/tabela1.py` | Table 1 |
| 14 | `tavi_savr/manuscrito/figuras_tavi.py` | Figures 1–4 |
| 15 | `tavi_savr/manuscrito/graphical_abstract.py` | Graphical abstract |

Map from the manuscript's supplementary tables to files: S2 `resultados_nacional/nacional_ano_faixa.csv`; S3 and S5
`resultados_auditoria/A2_A3_*`, `A3_*`; S4 `resultados_v2/resultados_v2.json`, `R2b_*`,
`resultados_modelo_uf/decomposicao_*`; S6 `resultados_auditoria/T1–T4`; S7 `resultados_geografia/taxas_uf_*`,
`resultados_v2/R4_*`; S8 `resultados_v2/R5_*`; S9 `resultados_v2/R6_*`, `resultados_geografia/deslocamento_*`; S10
`resultados_auditoria/A4_*`; S11 `resultados_nacional/mortalidade_2024_2025.csv`; S12 `resultados_fase1/por_grupo_ano.csv`;
S13–S15 `resultados_carga_capacidade/`; S16 `resultados_modelo_uf/`; S17 `resultados_nacional/distribuicao_etaria_pct.csv`;
S18 `resultados_judicializacao/`; S19 `resultados_v2/R3_*`; S20 `resultados_carga_capacidade/SIM_mortalidade_padronizada_*`.

**Reproducibility check.** Before publication every script was run inside this package on the pseudonymized data and
its outputs were compared with those of the original project (`pandas.testing.assert_frame_equal` for every CSV, after
applying the pseudonymization to the original identifiers). See *Verification* below.

## Definitions (summary)

- **TAVI**: SUS procedure codes 04.06.01.152-4 (Sep 2023–May 2024) and 04.06.03.016-2 (transfemoral TAVI, from May
  2024; Ordinance GM/MS 3.414/2024); private plans TUSS 30912296 (any access).
- **Aortic SAVR**: SUS 04.06.01.069-2 with aortic principal diagnosis (I35, I06, Q23.0, Q23.1) plus multiple-surgery
  hospitalizations (04.15.01.001-2, 04.15.02.003-4) with that procedure in the SP records; private plans TUSS 30902053
  without TAVI/combined codes, with the valve in three bounds (aortic diagnosis recorded; central imputation; all without
  a valve diagnosis).
- **Year** = year of admission (TISS: year of the event). **Denominators**: SUS = population without a private plan
  (population − beneficiaries); plans = beneficiaries. Direct age standardization to the 2022 Brazilian population
  (60–69, 70–79, ≥80).
- Hospital location is approximated by the centroid of the hospital's municipality, as is residence.

## Main variables

- `RD_valvas_2008_2026.csv.gz` (SIH/SUS RD layout): `N_AIH` (pseudonymous AIH code), `IDENT` (1 = main AIH),
  `PROC_REA` (procedure performed), `DIAG_PRINC`, `DIAGSEC1–9` (ICD-10), `IDADE`/`COD_IDADE` (age; code 4 = years,
  5 = 100+ years), `SEXO` (1 male, 3 female), `DT_INTER`/`DT_SAIDA` (dates), `CAR_INT` (01 elective, other = urgent),
  `CNES` (pseudonymous hospital code), `MUNIC_RES`/`MUNIC_MOV` (IBGE 6-digit municipality of residence/hospital),
  `MORTE` (in-hospital death), `DIAS_PERM` (length of stay), `VAL_TOT` (amount paid, BRL), `RACA_COR`, `GESTAO`,
  `COMPLEX`, `FINANC`, `ANO_CMPT`/`MES_CMPT` (processing month).
- `SP_multiplas_2008_2026.csv.gz`: `SP_NAIH` (pseudonymous AIH, same codes as `N_AIH`), `SP_CNES` (pseudonymous),
  `SP_PROCREA` (procedure of the AIH), `SP_ATOPROF` (procedure billed), `SP_DTINTER`, `SP_CIDPRI`.
- `tiss_valvas_2015_2025.csv.gz` (ANS TISS layout): `ID_EVENTO_ATENCAO_SAUDE` (open-data event id), `ID_PLANO`,
  `FAIXA_ETARIA` (10-year band), `SEXO`, `CD_MUNICIPIO_BENEFICIARIO`, `CD_MUNICIPIO_PRESTADOR`, `UF_PRESTADOR`,
  `ANO_MES_EVENTO`, `CD_CARATER_ATENDIMENTO` (1 elective, 2 urgent), `CD_MOTIVO_SAIDA` (41–43 = death), `CID_1–4`,
  `TEMPO_DE_PERMANENCIA`, `cods_tuss` (TUSS codes of the event, `;`-separated).
- `sim_valva_aortica_obitos.csv.gz` (SIM layout): `DTOBITO`, `IDADE` (4xx = years), `SEXO`, `CODMUNRES`, `CAUSABAS`,
  `LINHAA–LINHAD`, `LINHAII`.
- `tavi_savr/dados_ref/natjus_I35_procedimentos.csv`: e-NatJus note id, year, responsible technical centre, ICD, age,
  sex, state of the patient, court sphere, TAVI flag (the `plano_operadora` and `sus_mencionado` flags are 100% because
  they match template text and are not used).

## Privacy

Only public, anonymized administrative data were used. Hospital (CNES) and hospitalization (AIH) identifiers were
replaced by meaningless codes with a single random mapping that was not kept. Hospital names and coordinates were
removed. From the SP records, the identifiers of professionals (CNS, CPF/CNPJ) and all columns not used were removed.
The e-NatJus extract contains no names. No record links persons across data sets.

## What requires re-extraction from the public sources

The raw extraction scripts are included for transparency but are not run by `reproduce.sh`, because they download tens
of gigabytes: `sih_crvm.py` and `tavi_savr/extrair_valvas_sih.py` (RD), `tavi_savr/extrair_valvas_sp.py` (SP),
`tavi_savr/extrair_tiss_ans.py` (TISS), `tavi_savr/tiss_completude_planos.py` (TISS counts by plan),
`tavi_savr/ans_beneficiarios_junho.py` (June beneficiaries), `tavi_savr/natjus_tavi.py` (e-NatJus notes). Re-extraction
yields the real CNES/AIH identifiers; `tools/build_package_data.py` then rebuilds a package like this one with a new
random mapping. Hospital names (Supplementary Tables S8 and S10 of the manuscript) can only be recovered by
re-extraction and the public CNES API.

## Verification

On 14 November 2026, `reproduce.sh` was run in this package on the pseudonymized data. All 53 result tables (every CSV
in `tavi_savr/resultados_*/` and Table 1) and `resultados_v2/resultados_v2.json` were identical to those of the original
project (`pandas.testing.assert_frame_equal`, after replacing the original CNES/AIH codes and hospital names with the
package's pseudonymous codes). The only difference was the field `arquivos_parciais` of `resultados_fase1/resumo.json`
(number of input files: 1 consolidated file here versus 6,046 monthly files in the original). Figures were regenerated
from the same results; their files are not byte-compared (image metadata).

## License

Code: MIT (see `LICENSE`). Derived data and results: CC BY 4.0.

## Ethics

Public, anonymized data; under Brazilian National Health Council Resolution 510/2016 (Article 1, sole paragraph, items
II and III), no ethics committee approval or informed consent was required.

## Citation

See `CITATION.cff`. DOI: [to be added after the Zenodo release].
