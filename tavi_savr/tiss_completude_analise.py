#!/usr/bin/env python3
"""Completude do TISS: (1) planos continuamente observados (com internações em todos os anos 2021–2025) e série de TAVI e
troca valvar restrita a eles; (2) internações por mil beneficiários por UF e ano; (3) por UF, fração das internações com
CID I35 que têm algum procedimento valvar TUSS (TAVI 30912296 ou troca valvar 30902053) — indicador de faturamento
fora do código TUSS (pacote/tabela própria). Lê saida_tavi/tiss_planos/ e saida_tavi/tiss/. Saída: tavi_savr/resultados_auditoria/.
"""
import glob
import json
import os

import numpy as np
import pandas as pd

S = "tavi_savr/resultados_auditoria"
os.makedirs(S, exist_ok=True)

pl = pd.concat([pd.read_csv(f, dtype={"ID_PLANO": str}) for f in glob.glob("saida_tavi/tiss_planos/parciais/*.csv*")
                if os.path.getsize(f) > 0], ignore_index=True)
pa = pl.groupby(["ID_PLANO", "ano"])["internacoes"].sum().unstack(fill_value=0)
anos = list(range(2021, 2026))
cont = pa.index[(pa[anos] > 0).all(axis=1)]
tot = pa.sum()
share = pa.loc[cont].sum() / tot
c1 = pd.DataFrame({"internacoes_total": tot, "planos_com_internacao": (pa > 0).sum(),
                   "internacoes_planos_continuos_2021_2025": pa.loc[cont].sum(),
                   "pct_planos_continuos": (100 * share).round(1)})
c1.to_csv(f"{S}/T1_tiss_planos_continuos.csv")
print(c1.to_string())

ti = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False,
                            usecols=["ID_EVENTO_ATENCAO_SAUDE", "ID_PLANO", "FAIXA_ETARIA", "ANO_MES_EVENTO", "CID_1",
                                     "CID_2", "CID_3", "CID_4", "cods_tuss", "UF_PRESTADOR"])
                for f in glob.glob("saida_tavi/tiss/parciais/*.csv*") if os.path.getsize(f) > 0]).drop_duplicates(
    "ID_EVENTO_ATENCAO_SAUDE")
ti["ano"] = ti.ANO_MES_EVENTO.str[:4].astype(int)
c = ti.cods_tuss
ti["TAVI"] = c.str.contains("30912296")
ti["troca"] = c.str.contains("30902053") & ~c.str.contains("30912296|30903033|30902029")
ti["continuo"] = ti.ID_PLANO.isin(cont)
s = ti[ti.ano.isin(anos)].groupby(["ano", "continuo"])[["TAVI", "troca"]].sum().unstack()
s.columns = [f"{a}_{'continuos' if b else 'outros'}" for a, b in s.columns]
s["TAVI_pct_em_continuos"] = (100 * s.TAVI_continuos / (s.TAVI_continuos + s.TAVI_outros)).round(1)
fx = ti.FAIXA_ETARIA.str.extract(r"^(\d+)")[0].astype(float)
ti["faixa"] = np.select([fx >= 80, fx >= 70, fx >= 60], ["80+", "70-79", "60-69"], "<60")
dist = ti[ti.TAVI & ti.continuo & ti.ano.isin(anos)].groupby("ano")["faixa"].value_counts(normalize=True).unstack().mul(100).round(1)
s = s.join(dist.add_prefix("TAVI_continuos_pct_"))
s.to_csv(f"{S}/T2_tavi_troca_planos_continuos.csv")
print(s.to_string())

# internações por mil beneficiários por UF (UF do prestador = pasta do arquivo) e ano
uf_ev = pl.groupby(["uf", "ano"])["internacoes"].sum()
b = pd.read_csv("ciha/dados_ref/ans_beneficiarios_medicos_dezembro_uf.csv", dtype={"CD_FAIXA_E": str})
ben = b[b.CD_FAIXA_E.ne("99")].groupby(["SG_UF", "ano"])["NR_BENEF_M"].sum()
ben.index.names = ["uf", "ano"]
t3 = (1e3 * uf_ev / ben).round(1).unstack("ano")[anos]
t3.to_csv(f"{S}/T3_tiss_internacoes_por_mil_benef_uf.csv")

# I35 com procedimento valvar TUSS, por UF do prestador, 2023–2025, ≥70 anos
cids = ti[["CID_1", "CID_2", "CID_3", "CID_4"]].apply(lambda x: x.str.strip().str.upper())
i35 = cids.apply(lambda x: x.str.startswith("I35")).any(axis=1)
x = ti[i35 & ti.ano.between(2023, 2025) & ti.faixa.isin(["70-79", "80+"])]
t4 = x.groupby("UF_PRESTADOR").agg(internacoes_I35_70mais=("TAVI", "size"), com_TAVI=("TAVI", "sum"),
                                   com_troca=("troca", "sum"))
t4["pct_com_proc_valvar"] = (100 * (t4.com_TAVI + t4.com_troca) / t4.internacoes_I35_70mais).round(1)
t4 = t4.join(t3[2025].rename("internacoes_por_mil_benef_2025"))
t4.sort_values("pct_com_proc_valvar").to_csv(f"{S}/T4_tiss_I35_com_procedimento_por_uf.csv")
print(t4.sort_values("pct_com_proc_valvar").to_string())
