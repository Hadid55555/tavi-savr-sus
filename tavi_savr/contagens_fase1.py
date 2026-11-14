#!/usr/bin/env python3
"""Fase 1: contagens por ano de TAVI e SAVR aórtica no SIH/SUS (ano da internação) a partir dos parciais de
tavi_savr/extrair_valvas_sih.py. Gera tavi_savr/resultados_fase1/*.csv e um resumo em JSON.

Definições (provisórias, para o memo):
  TAVI        PROC_REA 0406011524 (ITVA, Portaria GM/MS 3.904/2022, excluído pela 3.414/2024) ou 0406030162
              (TAVI transfemoral, Portaria GM/MS 3.414/2024).
  SAVR isolada aórtica  0406010692 (implante de prótese valvar) com DIAG_PRINC aórtico: I35*, I06*, Q230, Q231.
  Outras com valva aórtica (sensibilidade): 0406010820 (plástica/troca múltipla), 0406011206 (troca valvar + CRVM),
              0406010846 (tubo valvado), com DIAG_PRINC aórtico; 0406011206 também com qualquer CID.
Só AIH IDENT = 1 (principal) nas contagens; IDENT 5 (longa permanência) é continuação da mesma internação.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

PASTA = sys.argv[1] if len(sys.argv) > 1 else "saida_tavi/parciais"
SAIDA = "tavi_savr/resultados_fase1"
os.makedirs(SAIDA, exist_ok=True)

USAR = ["ANO_CMPT", "MES_CMPT", "N_AIH", "IDENT", "PROC_REA", "MORTE", "IDADE", "COD_IDADE", "SEXO", "DT_INTER",
        "DIAG_PRINC", "CAR_INT", "CNES", "MUNIC_MOV", "MUNIC_RES", "COBRANCA", "DIAS_PERM", "VAL_TOT", "arquivo_origem"]
arqs = sorted(glob.glob(os.path.join(PASTA, "RD*.csv*")))
df = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=lambda c: c in USAR) for f in arqs],
               ignore_index=True)
for c in df.columns:
    df[c] = df[c].str.strip()
print("arquivos:", len(arqs), "registros:", len(df))

cod = df["COD_IDADE"]
idade = pd.to_numeric(df["IDADE"], errors="coerce")
df["idade"] = np.where(cod.eq("4"), idade, np.where(cod.eq("5"), 100 + idade, np.where(cod.isin(["2", "3"]), 0, np.nan)))
df["obito"] = pd.to_numeric(df["MORTE"], errors="coerce").fillna(0).astype(int)
df["ano"] = pd.to_datetime(df["DT_INTER"], format="%Y%m%d", errors="coerce").dt.year
df["mes_int"] = df["DT_INTER"].str[:6]
df["cmpt"] = df["ANO_CMPT"] + df["MES_CMPT"].str.zfill(2)
df["aortico"] = df["DIAG_PRINC"].str.match(r"^(I35|I06|Q23[01])")
df["cid3"] = df["DIAG_PRINC"].str[:3]

p = df["PROC_REA"]
df["grupo"] = None
df.loc[p.isin(["0406011524", "0406030162"]), "grupo"] = "TAVI"
df.loc[p.eq("0406010692") & df["aortico"], "grupo"] = "SAVR isolada (aórtica)"
df.loc[p.eq("0406010820") & df["aortico"], "grupo"] = "Múltipla/plástica com CID aórtico"
df.loc[p.eq("0406011206") & df["aortico"], "grupo"] = "Troca valvar + CRVM com CID aórtico"
df.loc[p.eq("0406010846") & df["aortico"], "grupo"] = "Tubo valvado com CID aórtico"
df.loc[p.eq("0406030111"), "grupo"] = "Valvoplastia aórtica percutânea"

princ = df[df["IDENT"].eq("1")]
print("IDENT:", df["IDENT"].value_counts().to_dict())

# 1. Códigos novos (faixas) e primeiro/último mês de cada código de TAVI
novos = princ[(p.loc[princ.index] >= "0406011520") & (p.loc[princ.index] <= "0406011999") |
              (p.loc[princ.index] >= "0406030160") & (p.loc[princ.index] <= "0406030299")]
cods = novos.groupby("PROC_REA").agg(n=("N_AIH", "size"), primeira_cmpt=("cmpt", "min"), ultima_cmpt=("cmpt", "max"),
                                    primeira_internacao=("mes_int", "min"), ultima_internacao=("mes_int", "max"),
                                    idade_mediana=("idade", "median"), pct_I35=("cid3", lambda s: round(100 * s.eq("I35").mean(), 1)))
cods.to_csv(f"{SAIDA}/codigos_novos.csv")
print(cods.to_string())


def resumo(g):
    a = g["idade"]
    return pd.Series({
        "n": len(g), "obitos": int(g["obito"].sum()), "mort_pct": round(100 * g["obito"].mean(), 1),
        "idade_media": round(a.mean(), 1), "idade_mediana": a.median(), "p25": a.quantile(.25), "p75": a.quantile(.75),
        "pct_lt65": round(100 * (a < 65).mean(), 1), "pct_65_74": round(100 * a.between(65, 74.999).mean(), 1),
        "pct_ge75": round(100 * (a >= 75).mean(), 1), "pct_fem": round(100 * g["SEXO"].isin(["2", "3"]).mean(), 1),
        "pct_I06_reumatica": round(100 * g["cid3"].eq("I06").mean(), 1),
        "pct_urgencia": round(100 * g["CAR_INT"].ne("01").mean(), 1),
        "hospitais": g["CNES"].nunique(), "ufs_atend": g["MUNIC_MOV"].str[:2].nunique()})


tab = princ[princ["grupo"].notna() & princ["ano"].between(2008, 2026)].groupby(["grupo", "ano"]).apply(resumo)
tab.to_csv(f"{SAIDA}/por_grupo_ano.csv")
pd.set_option("display.width", 250)
print(tab.to_string())

# 2. Faixa etária × ano: TAVI e SAVR isolada
fx = pd.cut(princ["idade"], [-1, 49, 59, 64, 69, 74, 79, 84, 200],
            labels=["<50", "50-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"])
fa = princ.assign(faixa=fx)[princ["grupo"].isin(["TAVI", "SAVR isolada (aórtica)"]) & princ["ano"].between(2008, 2026)]
fa.pivot_table(index=["grupo", "ano"], columns="faixa", values="N_AIH", aggfunc="size", fill_value=0,
               observed=False).to_csv(f"{SAIDA}/faixa_etaria_ano.csv")

# 3. CID principal do 0406010692 (quanto é aórtico), por ano
c692 = princ[princ["PROC_REA"].eq("0406010692") & princ["ano"].between(2008, 2026)]
c692.assign(cat=np.select([c692["cid3"].eq("I35"), c692["cid3"].eq("I06"), c692["DIAG_PRINC"].str.match(r"^Q23[01]"),
                           c692["cid3"].isin(["I34", "I05"]), c692["cid3"].isin(["I36", "I07", "I08"]),
                           c692["cid3"].isin(["I33", "I38", "I39"])],
                          ["I35", "I06", "Q230/Q231", "mitral (I34/I05)", "tricúspide/múltipla (I36/I07/I08)",
                           "endocardite/não especificada (I33/I38/I39)"], "outro")
            ).pivot_table(index="ano", columns="cat", values="N_AIH", aggfunc="size", fill_value=0).to_csv(
    f"{SAIDA}/proc_0406010692_por_cid_ano.csv")

# 4. Internações com CID aórtico sem procedimento valvar listado: o que foi faturado (top procedimentos, 2023–2025)
outros = princ[princ["aortico"] & princ["grupo"].isna() & princ["ano"].between(2023, 2025)]
outros["PROC_REA"].value_counts().head(25).to_csv(f"{SAIDA}/cid_aortico_outros_procedimentos_2023_2025.csv")

# 5. TAVI por hospital (CNES) e ano
princ[princ["grupo"].eq("TAVI")].pivot_table(index="CNES", columns="ano", values="N_AIH", aggfunc="size",
                                             fill_value=0).to_csv(f"{SAIDA}/tavi_cnes_ano.csv")

# 6. Conferência independente: contagem por competência de processamento 2025 (deve bater com
#    novas_pesquisas/procedimentos_0406_2025.csv, que contou todas as AIH processadas em 2025, sem filtro de IDENT)
c25 = df[df["ANO_CMPT"].eq("2025")]
conf = {}
ref = pd.read_csv("novas_pesquisas/procedimentos_0406_2025.csv", dtype={"PROC_REA": str}).set_index("PROC_REA")
for c in ["0406030162", "0406010692", "0406010820", "0406011206", "0406010846", "0406030111"]:
    sub = c25[c25["PROC_REA"].eq(c)]
    conf[c] = {"n_aqui": len(sub), "n_levantamento": int(ref.loc[c, "n"]), "obitos_aqui": int(sub["obito"].sum()),
               "obitos_levantamento": int(ref.loc[c, "obitos"]), "hosp_aqui": sub["CNES"].nunique(),
               "hosp_levantamento": int(ref.loc[c, "hosp"])}
print(json.dumps(conf, indent=1))
json.dump({"arquivos_parciais": len(arqs), "registros": len(df), "conferencia_2025_cmpt": conf},
          open(f"{SAIDA}/resumo.json", "w"), indent=1, ensure_ascii=False)
