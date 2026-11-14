#!/usr/bin/env python3
"""Sensibilidade da razão de TAVI planos/SUS (2025, ≥60, padronizada) à sobreposição de denominadores: estratos de UF
por cobertura de planos ≥60 (tercis) e exclusão do tercil de maior cobertura. Reaproveita dados/funções de
analises_v2.py (mesmos numeradores e denominadores do R2). Saída: resultados_v2/R2b_sensibilidade_cobertura.csv."""
import os, sys, types
import pandas as pd
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
src = open("tavi_savr/analises_v2.py", encoding="utf-8").read()
src = src[:src.index('saida["R2_todas_UFs"]')]          # só carga de dados + funções do R2
ns = {"__name__": "r2"}
exec(compile(src, "analises_v2_parcial", "exec"), ns)
den, taxas = ns["den"], ns["taxas"]
cob = (den.groupby(level="uf").benef.sum() / den.groupby(level="uf")["pop"].sum()).sort_values()
cob = cob[cob.index.isin(list(ns["UF_IBGE"].values()))]
ters = pd.qcut(cob, 3, labels=["baixa", "media", "alta"])
linhas = []
def add(nome, excl):
    o = taxas(tuple(excl))
    linhas.append({"analise": nome, "ufs_excluidas": ",".join(sorted(excl)),
                   "SUS_sem_plano": o["SUS_sem_plano"]["taxa"], "Planos": o["Planos_beneficiarios"]["taxa"],
                   "razao": o["razao_planos_vs_SUS_sem_plano"]["razao"], "ic_inf": o["razao_planos_vs_SUS_sem_plano"]["ic95"][0],
                   "ic_sup": o["razao_planos_vs_SUS_sem_plano"]["ic95"][1],
                   "razao_pop_total": o["razao_planos_vs_SUS_pop_total"]["razao"]})
add("Todas as UFs", [])
add("Sem CE, AP, RO (codificação TISS)", ["CE", "AP", "RO"])
add("Sem tercil de maior cobertura de planos", list(ters[ters == "alta"].index))
for t in ["baixa", "media", "alta"]:
    add(f"Só UFs de cobertura {t} ({cob[ters == t].min():.0%}–{cob[ters == t].max():.0%})", list(ters[ters != t].index))
r = pd.DataFrame(linhas)
r.to_csv("tavi_savr/resultados_v2/R2b_sensibilidade_cobertura.csv", index=False)
print(r.to_string()); print(cob.round(3).to_dict())
