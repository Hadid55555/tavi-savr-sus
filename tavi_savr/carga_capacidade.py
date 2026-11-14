#!/usr/bin/env python3
"""Carga de doença (SIM) e capacidade instalada (CNES) por UF, para contextualizar o acesso à TAVI.

Fontes (compilação pública Kaggle rafatrindade/brazilian-kaggle-datahub, a partir dos .dbc do DATASUS; o FTP do
DATASUS não responde deste ambiente):
  sim/declaracoes_de_obito_cid10.parquet (DO 1996+);  cnes/habilitacoes.parquet (competência set/2026).
SIM: óbitos com causa básica I35 (doença não reumática da valva aórtica; I35.0 estenose, I35.2 estenose + insuficiência)
e óbitos com I35 em qualquer linha da DO (causa múltipla), por ano, idade (≥60/≥70) e UF de residência.
Índice de acesso por UF (2023–2025, ≥70 anos): trocas aórticas (TAVI + SAVR aórtica, SUS + planos, por UF de residência)
por óbito com causa básica I35 — denominador que não depende de cobertura de plano (proxy de carga, não de necessidade).
CNES: hospitais com habilitação 08.15 (TAVI), 08.01/08.02 (alta complexidade cardiovascular) e 08.03 por UF, com data
de início (CMPT_INI) e portaria.
Saída: tavi_savr/resultados_carga_capacidade/.
"""
import glob
import os

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

K = "saida_tavi/kaggle_raw"
S = "tavi_savr/resultados_carga_capacidade"
os.makedirs(S, exist_ok=True)
UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
           "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
           "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}

# ---------- SIM ----------
cols = ["DTOBITO", "IDADE", "SEXO", "CODMUNRES", "CAUSABAS", "LINHAA", "LINHAB", "LINHAC", "LINHAD", "LINHAII"]
PARQ = f"{K}/sim_declaracoes_de_obito_cid10.parquet"
if os.path.exists(PARQ):
    f = pq.ParquetFile(PARQ)
    partes, total = [], 0
    for i in range(f.metadata.num_row_groups):
        t = f.read_row_group(i, columns=cols)
        total += t.num_rows
        m = pc.starts_with(pc.utf8_upper(pc.fill_null(t["CAUSABAS"].cast(pa.string()), "")), "I35")
        for c in cols[5:]:
            m = pc.or_(m, pc.match_substring(pc.utf8_upper(pc.fill_null(t[c].cast(pa.string()), "")), "I35"))
        t = t.filter(m)
        if t.num_rows:
            partes.append(t.to_pandas())
    sim = pd.concat(partes, ignore_index=True).astype(str)
else:  # pacote público: extrato do SIM já filtrado (I35/I06 em qualquer campo), gerado por sim_mortalidade_padronizada.py
    sim = pd.read_csv("saida_tavi/sim_valva_aortica_obitos.csv.gz", dtype=str, keep_default_na=False)[cols]
    m = sim.CAUSABAS.str.upper().str.startswith("I35")
    for c in cols[5:]:
        m = m | sim[c].str.upper().str.contains("I35", regex=False)
    sim = sim[m].reset_index(drop=True)
    total = float("nan")
sim["ano"] = sim.DTOBITO.str.zfill(8).str[-4:]
ida = sim.IDADE.str.zfill(3)
sim["idade"] = np.where(ida.str[0].eq("4"), pd.to_numeric(ida.str[1:], errors="coerce"),
                        np.where(ida.str[0].eq("5"), 100 + pd.to_numeric(ida.str[1:], errors="coerce"), np.nan))
sim["uf"] = sim.CODMUNRES.str[:2].map(UF_IBGE)
sim["basica_I35"] = sim.CAUSABAS.str.upper().str.startswith("I35")
sim["basica_EA"] = sim.CAUSABAS.str.upper().isin(["I350", "I352"])
print("DO lidas:", total, "| com I35 em alguma linha:", len(sim))
s1 = sim[sim.ano.between("2008", "2025")].groupby("ano").agg(
    obitos_I35_qualquer_linha=("ano", "size"), obitos_basica_I35=("basica_I35", "sum"),
    obitos_basica_EA=("basica_EA", "sum"),
    basica_I35_70mais=("basica_I35", lambda s: int((s & (sim.loc[s.index, "idade"] >= 70)).sum())),
    idade_mediana_basica=("idade", lambda s: s[sim.loc[s.index, "basica_I35"]].median()))
s1.to_csv(f"{S}/SIM_obitos_I35_ano.csv")
print(s1.to_string())

# ---------- índice de acesso por UF (2023–2025, ≥70) ----------
ob = sim[sim.basica_I35 & (sim.idade >= 70) & sim.ano.isin(["2023", "2024", "2025"])].groupby(["uf", "ano"]).size()
rd = pd.concat([pd.read_csv(x, dtype=str, keep_default_na=False,
                            usecols=["N_AIH", "IDENT", "PROC_REA", "DIAG_PRINC", "IDADE", "COD_IDADE", "DT_INTER", "MUNIC_RES"])
                for x in glob.glob("saida_tavi/parciais/RD*.csv*") if os.path.getsize(x) > 0]).apply(lambda s: s.str.strip())
rd = rd[rd.IDENT.eq("1")]
i = pd.to_numeric(rd.IDADE, errors="coerce")
rd["idade"] = np.where(rd.COD_IDADE.eq("4"), i, np.where(rd.COD_IDADE.eq("5"), 100 + i, np.nan))
rd["ano"] = rd.DT_INTER.str[:4]
rd["uf"] = rd.MUNIC_RES.str[:2].map(UF_IBGE)
sp = pd.concat([pd.read_csv(x, dtype=str, keep_default_na=False, usecols=["SP_NAIH", "SP_PROCREA", "SP_ATOPROF"])
                for x in glob.glob("saida_tavi/sp/parciais/SP*.csv*") if os.path.getsize(x) > 0]).apply(lambda s: s.str.strip())
mult = set(sp.loc[sp.SP_PROCREA.isin(["0415010012", "0415020034"]) & sp.SP_ATOPROF.eq("0406010692"), "SP_NAIH"])
p = rd.PROC_REA
aort = rd.DIAG_PRINC.str.match(r"^(I35|I06|Q23[01])")
rd["g"] = np.select([p.isin(["0406011524", "0406030162"]),
                     aort & (p.eq("0406010692") | (p.isin(["0415010012", "0415020034"]) & rd.N_AIH.isin(mult)))],
                    ["TAVI", "SAVR"], "")
sus = rd[rd.g.ne("") & (rd.idade >= 70) & rd.ano.isin(["2023", "2024", "2025"])].groupby(["uf", "g"]).size().unstack(fill_value=0)
ti = pd.concat([pd.read_csv(x, dtype=str, keep_default_na=False) for x in glob.glob("saida_tavi/tiss/parciais/*.csv*")
                if os.path.getsize(x) > 0]).drop_duplicates("ID_EVENTO_ATENCAO_SAUDE")
fx = ti.FAIXA_ETARIA.str.extract(r"^(\d+)")[0].astype(float)
c = ti.cods_tuss
cids = ti[["CID_1", "CID_2", "CID_3", "CID_4"]].apply(lambda s: s.str.strip().str.upper())
ti_aort = cids.apply(lambda s: s.str.match(r"^(I35|I06|Q23[01])")).any(axis=1)
ti["g"] = np.select([c.str.contains("30912296"), c.str.contains("30902053") & ~c.str.contains("30903033|30902029") & ti_aort],
                    ["TAVI", "SAVR"], "")
ti["uf"] = ti.CD_MUNICIPIO_BENEFICIARIO.str[:2].map(UF_IBGE)
pl = ti[ti.g.ne("") & (fx >= 70) & ti.ANO_MES_EVENTO.str[:4].isin(["2023", "2024", "2025"])].groupby(["uf", "g"]).size().unstack(fill_value=0)
ix = pd.DataFrame({"obitos_I35_basica_70mais": ob.groupby(level="uf").sum(),
                   "TAVI_SUS": sus.get("TAVI"), "SAVR_SUS": sus.get("SAVR"),
                   "TAVI_planos": pl.get("TAVI"), "SAVR_planos_CIDexplicito": pl.get("SAVR")}).fillna(0)
ix["AVR_total"] = ix[["TAVI_SUS", "SAVR_SUS", "TAVI_planos", "SAVR_planos_CIDexplicito"]].sum(axis=1)
ix["AVR_por_obito"] = (ix.AVR_total / ix.obitos_I35_basica_70mais).round(2)
ix["TAVI_por_obito"] = ((ix.TAVI_SUS + ix.TAVI_planos) / ix.obitos_I35_basica_70mais).round(2)
ix["TAVI_SUS_por_obito"] = (ix.TAVI_SUS / ix.obitos_I35_basica_70mais).round(2)
ix.loc["Brasil"] = ix.drop(index=[u for u in ix.index if u == "Brasil"]).sum()
ix.loc["Brasil", ["AVR_por_obito", "TAVI_por_obito", "TAVI_SUS_por_obito"]] = [
    round(ix.loc["Brasil", "AVR_total"] / ix.loc["Brasil", "obitos_I35_basica_70mais"], 2),
    round((ix.loc["Brasil", "TAVI_SUS"] + ix.loc["Brasil", "TAVI_planos"]) / ix.loc["Brasil", "obitos_I35_basica_70mais"], 2),
    round(ix.loc["Brasil", "TAVI_SUS"] / ix.loc["Brasil", "obitos_I35_basica_70mais"], 2)]
ix.sort_values("AVR_por_obito").to_csv(f"{S}/indice_AVR_por_obito_I35_uf_2023_2025.csv")
print(ix.sort_values("AVR_por_obito").to_string())

# ---------- CNES habilitações ----------
hb = pq.read_table(f"{K}/cnes_habilitacoes.parquet").to_pandas().astype(str)
hb["uf"] = hb.CODUFMUN.str[:2].map(UF_IBGE)
alvo = {"0815": "TAVI (08.15)", "0801": "Unidade AC cardiovascular (08.01)", "0802": "Centro ref. AC cardiovascular (08.02)",
        "0803": "Cirurgia CV + intervencionista (08.03)"}
h = hb[hb.SGRUPHAB.isin(alvo) & hb.CMPT_FIM.isin(["999999", "nan", ""])]
cap = h.pivot_table(index="uf", columns="SGRUPHAB", values="CNES", aggfunc="nunique", fill_value=0).rename(columns=alvo)
cap = cap.reindex(sorted(UF_IBGE.values())).fillna(0).astype(int)
cap.loc["Brasil"] = h.groupby("SGRUPHAB").CNES.nunique().rename(alvo)
cap.to_csv(f"{S}/CNES_habilitacoes_cardio_uf_set2026.csv")
h[h.SGRUPHAB.eq("0815")][["CNES", "uf", "CMPT_INI", "PORTARIA", "DTPORTAR"]].sort_values("CMPT_INI").to_csv(
    f"{S}/CNES_hospitais_0815.csv", index=False)
print(cap.to_string())
print(h[h.SGRUPHAB.eq("0815")][["CNES", "uf", "CMPT_INI", "PORTARIA"]].sort_values("CMPT_INI").to_string())
