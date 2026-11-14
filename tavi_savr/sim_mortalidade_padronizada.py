#!/usr/bin/env python3
"""Mortalidade por estenose aórtica no Brasil, 2008–2025, padronizada por idade — comparável a Siddiqi 2026 (JACC Adv,
EUA, CDC WONDER) e Hartley 2021 (Europa, OMS).

Definição (= Siddiqi): óbitos ≥45 anos com I35.0, I35.2, I06.0 ou I06.2 como causa básica OU em qualquer linha da DO
(causa múltipla); sensibilidade só causa básica. Padronização direta para a população-padrão dos EUA de 2000 (faixas
45–54, 55–64, 65–74 e ≥75 — 75–84 e ≥85 fundidas porque a projeção do IBGE de 2008–09 só tem "80 anos ou mais").
Taxas por 100 mil; joinpoint não usado — AAPC por regressão log-linear (Poisson) do ano, com IC 95%.
Também por região (UF de residência) e capitais × interior (município de residência = capital da UF; denominador por
município não disponível → só proporção de óbitos e razão de taxas brutas não calculada).
Fontes: SIM (Kaggle datahub, DO 1996–2026); IBGE projeção rev. 2018 (artigo/dados_ref/proj7358.json).
Saída: tavi_savr/resultados_carga_capacidade/SIM_mortalidade_padronizada*.csv
"""
import json
import os

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
S = "tavi_savr/resultados_carga_capacidade"
CACHE = next((x for x in ["saida_tavi/sim_valva_aortica_obitos.csv.gz", "saida_tavi/sim_valva_aortica_obitos.csv"]
              if os.path.exists(x)), "saida_tavi/sim_valva_aortica_obitos.csv")
UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
           "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
           "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
REG = {**{u: "Norte" for u in ["RO", "AC", "AM", "RR", "PA", "AP", "TO"]},
       **{u: "Nordeste" for u in ["MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA"]},
       **{u: "Sudeste" for u in ["MG", "ES", "RJ", "SP"]}, **{u: "Sul" for u in ["PR", "SC", "RS"]},
       **{u: "Centro-Oeste" for u in ["MS", "MT", "GO", "DF"]}}
CAPITAIS = {"110020", "120040", "130260", "140010", "150140", "160030", "172100", "211130", "221100", "230440", "240810",
            "250750", "261160", "270430", "280030", "292740", "310620", "320530", "330455", "355030", "410690", "420540",
            "431490", "500270", "510340", "520870", "530010"}
CODS = ("I350", "I352", "I060", "I062")
# população-padrão EUA 2000 (Census, P25-1130), faixas ≥45
US2000 = {"45-54": 37030152, "55-64": 23961506, "65-74": 18135514, "75+": 12314793 + 4259173}
W = pd.Series(US2000) / sum(US2000.values())

if not os.path.exists(CACHE):
    cols = ["DTOBITO", "IDADE", "SEXO", "CODMUNRES", "CAUSABAS", "LINHAA", "LINHAB", "LINHAC", "LINHAD", "LINHAII"]
    f = pq.ParquetFile("saida_tavi/kaggle_raw/sim_declaracoes_de_obito_cid10.parquet")
    partes = []
    for i in range(f.metadata.num_row_groups):
        t = f.read_row_group(i, columns=cols)
        m = None
        for c in cols[4:]:
            s = pc.utf8_upper(pc.fill_null(t[c].cast(pa.string()), ""))
            for k in ("I35", "I06"):
                mm = pc.match_substring(s, k)
                m = mm if m is None else pc.or_(m, mm)
        t = t.filter(m)
        if t.num_rows:
            partes.append(t.to_pandas().astype(str))
    pd.concat(partes, ignore_index=True).to_csv(CACHE, index=False)
d = pd.read_csv(CACHE, dtype=str, keep_default_na=False)
d["ano"] = d.DTOBITO.str.zfill(8).str[-4:].astype(int)
ida = d.IDADE.str.zfill(3)
d["idade"] = np.where(ida.str[0].eq("4"), pd.to_numeric(ida.str[1:], errors="coerce"),
                      np.where(ida.str[0].eq("5"), 100 + pd.to_numeric(ida.str[1:], errors="coerce"), np.nan))
linhas = d[["LINHAA", "LINHAB", "LINHAC", "LINHAD", "LINHAII"]].apply(lambda s: s.str.upper().str.replace("*", " ", regex=False))
qualquer = linhas.apply(lambda s: s.str.contains("|".join(CODS))).any(axis=1)
basica = d.CAUSABAS.str.upper().str[:4].isin(CODS)
d["mult"] = qualquer | basica
d["bas"] = basica
d["fx"] = pd.cut(d.idade, [44.99, 54.99, 64.99, 74.99, 200], labels=list(US2000)).astype(str)
d["uf"] = d.CODMUNRES.str[:2].map(UF_IBGE)
d["regiao"] = d.uf.map(REG)
d["capital"] = d.CODMUNRES.str[:6].isin(CAPITAIS)
d = d[d.ano.between(2008, 2025) & d.fx.isin(list(US2000))]

p = pd.DataFrame(json.load(open("artigo/dados_ref/proj7358.json"))[1:])
p["V"] = pd.to_numeric(p.V, errors="coerce")
p["ano"] = p.D6N.astype(int)
p["uf"] = p.D1C.map(UF_IBGE)
mapa = {"45 a 49 anos": "45-54", "50 a 54 anos": "45-54", "55 a 59 anos": "55-64", "60 a 64 anos": "55-64",
        "65 a 69 anos": "65-74", "70 a 74 anos": "65-74", "75 a 79 anos": "75+", "80 anos ou mais": "75+",
        "80 a 84 anos": "75+", "85 a 89 anos": "75+", "90 anos ou mais": "75+"}
p["fx"] = p.D5N.map(mapa)
# evitar dupla contagem: em anos com faixas 80–84/85–89/90+ não usar "80 anos ou mais" (e vice-versa)
tem_det = p[p.D5N.eq("80 a 84 anos") & p.V.notna() & p.V.gt(0)].groupby(["ano", "uf"]).size()
p = p[p.fx.notna()]
p = p[~(p.D5N.eq("80 anos ou mais") & p.set_index(["ano", "uf"]).index.isin(tem_det.index))]
pop = p.groupby(["ano", "uf", "fx"]).V.sum()
pop.name = "pop"


def taxa(obitos, popf):
    """Taxa padronizada por 100 mil com IC 95% (gama, Fay–Feuer)."""
    from scipy import stats
    o, n = obitos.reindex(W.index).fillna(0), popf.reindex(W.index)
    wi = W / n
    y = float((wi * o).sum()); v = float((wi ** 2 * o).sum()); wm = float(wi.max())
    lo = stats.gamma.ppf(0.025, y ** 2 / v, scale=v / y) if y > 0 else 0
    hi = stats.gamma.ppf(0.975, (y + wm) ** 2 / (v + wm ** 2), scale=(v + wm ** 2) / (y + wm))
    return 1e5 * y, 1e5 * lo, 1e5 * hi


rows = []
for grupo, filt in [("Brasil", None)] + [(r, r) for r in ["Norte", "Nordeste", "Sudeste", "Sul", "Centro-Oeste"]]:
    for defin in ["mult", "bas"]:
        for ano in range(2008, 2026):
            dd = d[(d.ano == ano) & d[defin]]
            pp = pop.loc[ano]
            if filt:
                dd = dd[dd.regiao.eq(filt)]
                pp = pp[pp.index.get_level_values("uf").map(REG) == filt]
            o = dd.groupby("fx").size()
            n = pp.groupby(level="fx").sum()
            t, lo, hi = taxa(o, n)
            esp = {f"taxa_{k}": round(1e5 * o.get(k, 0) / n[k], 2) for k in W.index}
            rows.append({"grupo": grupo, "definicao": "causa multipla" if defin == "mult" else "causa basica", "ano": ano,
                         "obitos": int(o.sum()), "taxa_padr_100mil": round(t, 2), "ic_inf": round(lo, 2),
                         "ic_sup": round(hi, 2), **esp})
r = pd.DataFrame(rows)
r.to_csv(f"{S}/SIM_mortalidade_padronizada_EA.csv", index=False)


def aapc(sub, col="taxa_padr_100mil"):
    x = sub.ano.values - sub.ano.min(); y = np.log(sub[col].clip(lower=1e-6).values)
    b, a = np.polyfit(x, y, 1)
    res = y - (a + b * x); se = np.sqrt((res ** 2).sum() / (len(x) - 2) / ((x - x.mean()) ** 2).sum())
    return round(100 * (np.exp(b) - 1), 2), round(100 * (np.exp(b - 1.96 * se) - 1), 2), round(100 * (np.exp(b + 1.96 * se) - 1), 2)


res = []
for (g, df_), sub in r.groupby(["grupo", "definicao"]):
    for per, (a0, a1) in {"2008-2025": (2008, 2025), "2008-2019": (2008, 2019), "2019-2025": (2019, 2025)}.items():
        s = sub[sub.ano.between(a0, a1)]
        ap = aapc(s)
        row = {"grupo": g, "definicao": df_, "periodo": per, "taxa_inicio": s.iloc[0].taxa_padr_100mil,
               "taxa_fim": s.iloc[-1].taxa_padr_100mil, "AAPC_pct": ap[0], "IC_inf": ap[1], "IC_sup": ap[2]}
        for k in W.index:
            row[f"AAPC_{k}"] = aapc(s, f"taxa_{k}")[0]
        res.append(row)
res = pd.DataFrame(res)
res.to_csv(f"{S}/SIM_mortalidade_padronizada_EA_tendencia.csv", index=False)
cap = d[d.mult].groupby("ano").capital.mean().mul(100).round(1).rename("pct_obitos_em_capitais")
cap.to_csv(f"{S}/SIM_mortalidade_EA_pct_capitais.csv")
pd.set_option("display.width", 250)
print(r[(r.grupo == "Brasil")].to_string())
print(res.to_string())
print(cap.to_string())
