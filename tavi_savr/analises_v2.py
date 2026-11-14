#!/usr/bin/env python3
"""Análises pedidas na segunda opinião v2 (31/out/2026). Saída: tavi_savr/resultados_v2/.

R1  Auditoria dos numeradores: AIH duplicadas no SUS; IDs repetidos no TISS; TAVI com CID de prótese (valve-in-valve).
R2  Taxas de TAVI 2025 (≥60 anos) padronizadas por idade (padrão: população brasileira de 2022, faixas 60–69/70–79/≥80),
    com IC 95% (método gama de Fay & Feuer) e razão planos/SUS (IC por delta no log), para três denominadores do SUS
    (sem plano; população total) e beneficiários nos planos; sensibilidade excluindo UFs de residência com baixa
    codificação de procedimento valvar no TISS (<20% das internações I35 ≥70 anos com TAVI/troca: CE, AP, RO).
R3  Série mensal de TAVI (SUS por mês de internação; planos por mês do evento) com marcos regulatórios (figura).
R4  Desigualdade entre UFs (taxas padronizadas ≥60, 2025): Gini e Theil ponderados pela população de referência;
    % da população ≥60 vivendo em UF com taxa SUS 0, <1, <5 por milhão.
R5  Implantação: 25 hospitais habilitados pela Portaria GM/MS 3.414/2024 — mês do primeiro TAVI, % com ≥1 TAVI em
    6/12/18 meses a partir de mai/2024, volume 2024–2025.
R6  Distância (geodésica) do município de residência ao centro SUS de TAVI ativo mais próximo (≥10 TAVI em 2024–25),
    para pacientes SUS com SAVR aórtica ≥70 anos e TAVI 2024–25, por região.
R7  TAVI SUS <75 anos: por idade em 5 anos, código e período (antes/depois de mai/2024).
"""
import glob
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

S = "tavi_savr/resultados_v2"
os.makedirs(S, exist_ok=True)
FAIXAS = ["60-69", "70-79", "80+"]
UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
           "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
           "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
REGIAO = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}
HABILITADOS = ["H825548", "H445809", "H941310", "H610743", "H272292", "H307558", "H824600", "H395775", "H160893",
               "H982039", "H498453", "H669060", "H697973", "H754044", "H494491", "H230365", "H604113", "H704348",
               "H222746", "H112275", "H686283", "H693240", "H238945", "H820290", "H912286"]
saida = {}

# ---------- dados ----------
cols = ["N_AIH", "IDENT", "PROC_REA", "DIAG_PRINC", "IDADE", "COD_IDADE", "DT_INTER", "CNES", "MUNIC_RES", "MUNIC_MOV",
        "CAR_INT"] + [f"DIAGSEC{i}" for i in range(1, 10)]
rd = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=lambda c: c in cols)
                for f in glob.glob("saida_tavi/parciais/RD*.csv*") if os.path.getsize(f) > 0]).apply(lambda s: s.str.strip())
i = pd.to_numeric(rd.IDADE, errors="coerce")
rd["idade"] = np.where(rd.COD_IDADE.eq("4"), i, np.where(rd.COD_IDADE.eq("5"), 100 + i, np.nan))
rd["mes"] = rd.DT_INTER.str[:6]
rd["ano"] = rd.DT_INTER.str[:4].astype(int)
tavi_all = rd[rd.PROC_REA.isin(["0406011524", "0406030162"])]
tavi = tavi_all[tavi_all.IDENT.eq("1")].copy()
tavi["faixa"] = pd.cut(tavi.idade, [-1, 59.99, 69.99, 79.99, 200], labels=["<60"] + FAIXAS).astype(str)
tavi["uf_res"] = tavi.MUNIC_RES.str[:2].map(UF_IBGE)

ti = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in glob.glob("saida_tavi/tiss/parciais/*.csv*")
                if os.path.getsize(f) > 0])
ids_rep = int(ti.ID_EVENTO_ATENCAO_SAUDE.duplicated().sum())
ti = ti.drop_duplicates("ID_EVENTO_ATENCAO_SAUDE")
tt = ti[ti.cods_tuss.str.contains("30912296")].copy()
fx = tt.FAIXA_ETARIA.str.extract(r"^(\d+)")[0].astype(float)
tt["faixa"] = np.select([fx >= 80, fx >= 70, fx >= 60], FAIXAS[::-1], "<60")
tt["uf_res"] = tt.CD_MUNICIPIO_BENEFICIARIO.str[:2].map(UF_IBGE)
tt["ano"] = tt.ANO_MES_EVENTO.str[:4].astype(int)
tt["mes"] = tt.ANO_MES_EVENTO.str.replace("-", "").str[:6]

# ---------- R1 ----------
viv = r"^(T820|T826|Z952)"
dx_sus = tavi[["DIAG_PRINC"] + [f"DIAGSEC{k}" for k in range(1, 10)]]
dx_ti = tt[["CID_1", "CID_2", "CID_3", "CID_4"]].apply(lambda s: s.str.upper())
saida["R1"] = {
    "SUS_TAVI_AIH_IDENT1": len(tavi), "SUS_TAVI_AIH_IDENT5": int((tavi_all.IDENT == "5").sum()),
    "SUS_N_AIH_repetido": int(tavi.N_AIH.duplicated().sum()),
    "TISS_IDs_repetidos_entre_arquivos": ids_rep, "TISS_TAVI_eventos": len(tt),
    "SUS_TAVI_com_CID_protese": int(dx_sus.apply(lambda s: s.str.match(viv)).any(axis=1).sum()),
    "TISS_TAVI_com_CID_protese": int(dx_ti.apply(lambda s: s.str.match(viv)).any(axis=1).sum()),
    "TISS_TAVI_com_CID_preenchido": int(dx_ti.ne("").any(axis=1).sum()),
}

# ---------- denominadores por UF × faixa (2025) e padrão ----------
pop = pd.read_csv("artigo/dados_ref/populacao_uf_ano_faixa.csv")
padrao = pop[(pop.ano == 2022) & pop.faixa.isin(FAIXAS)].groupby("faixa")["pop"].sum()
W = (padrao / padrao.sum()).reindex(FAIXAS)
pop25 = pop[(pop.ano == 2025) & pop.faixa.isin(FAIXAS)].set_index(["uf", "faixa"])["pop"]
b = pd.read_csv("ciha/dados_ref/ans_beneficiarios_medicos_dezembro_uf.csv", dtype={"CD_FAIXA_E": str})
b = b[(b.ano == 2025) & b.CD_FAIXA_E.ne("99")]
cf = b.CD_FAIXA_E.astype(int)
b["faixa"] = np.select([cf >= 26, cf >= 24, cf >= 22], ["80+", "70-79", "60-69"], "<60")
ben25 = b[b.faixa.isin(FAIXAS)].groupby(["SG_UF", "faixa"]).NR_BENEF_M.sum()
ben25.index.names = ["uf", "faixa"]
den = pd.DataFrame({"pop": pop25, "benef": ben25}).fillna(0)
den["sem_plano"] = den["pop"] - den["benef"]


def dsr(cont, popf):
    """Taxa padronizada direta por milhão com IC 95% (Fay & Feuer 1997). cont, popf: Series por faixa."""
    cont, popf = cont.reindex(FAIXAS).fillna(0), popf.reindex(FAIXAS)
    wi = W / popf
    y = float((wi * cont).sum())
    v = float((wi ** 2 * cont).sum())
    wm = float(wi.max())
    lo = stats.gamma.ppf(0.025, y ** 2 / v, scale=v / y) if y > 0 else 0.0
    hi = stats.gamma.ppf(0.975, (y + wm) ** 2 / (v + wm ** 2), scale=(v + wm ** 2) / (y + wm))
    return 1e6 * y, 1e6 * lo, 1e6 * hi, v


def razao(a, b_):
    (ya, _, _, va), (yb, _, _, vb) = a, b_
    r = ya / yb
    se = np.sqrt(va / (ya / 1e6) ** 2 + vb / (yb / 1e6) ** 2)
    return r, r * np.exp(-1.96 * se), r * np.exp(1.96 * se)


# ---------- R2 ----------
def taxas(ufs_excluir=()):
    ok = [u for u in UF_IBGE.values() if u not in ufs_excluir]
    d = den[den.index.get_level_values("uf").isin(ok)].groupby(level="faixa").sum()
    s = tavi[(tavi.ano == 2025) & tavi.uf_res.isin(ok)].groupby("faixa").size()
    p = tt[(tt.ano == 2025) & tt.uf_res.isin(ok)].groupby("faixa").size()
    r = {"SUS_sem_plano": dsr(s, d.sem_plano), "SUS_pop_total": dsr(s, d["pop"]), "Planos_beneficiarios": dsr(p, d.benef)}
    out = {k: {"taxa": round(v[0], 1), "ic95": [round(v[1], 1), round(v[2], 1)]} for k, v in r.items()}
    for k in ["SUS_sem_plano", "SUS_pop_total"]:
        rr = razao(r["Planos_beneficiarios"], r[k])
        out[f"razao_planos_vs_{k}"] = {"razao": round(rr[0], 2), "ic95": [round(rr[1], 2), round(rr[2], 2)]}
    out["especificas"] = {f: {"SUS_n": int(s.get(f, 0)), "Planos_n": int(p.get(f, 0)),
                              "SUS_pm_sem_plano": round(1e6 * s.get(f, 0) / d.sem_plano[f], 1),
                              "SUS_pm_pop_total": round(1e6 * s.get(f, 0) / d["pop"][f], 1),
                              "Planos_pm": round(1e6 * p.get(f, 0) / d.benef[f], 1)} for f in FAIXAS}
    return out


saida["R2_todas_UFs"] = taxas()
saida["R2_sem_CE_AP_RO"] = taxas(("CE", "AP", "RO"))
saida["R2_padrao_pesos"] = {f: round(float(W[f]), 4) for f in FAIXAS}
saida["R2_SUS_sem_UF_residencia"] = int(tavi[(tavi.ano == 2025)].uf_res.isna().sum())
saida["R2_planos_sem_UF_residencia"] = int(tt[(tt.ano == 2025)].uf_res.isna().sum())

# ---------- R3 ----------
ms = tavi.groupby("mes").size()
mp = tt.groupby("mes").size()
meses = pd.period_range("2021-01", "2026-08", freq="M").strftime("%Y%m")
serie = pd.DataFrame({"SUS": ms.reindex(meses).fillna(0), "Planos": mp.reindex(meses)}).astype(float)
serie.loc[serie.index > "202512", "Planos"] = np.nan
serie.to_csv(f"{S}/R3_serie_mensal_tavi.csv")
fig, ax = plt.subplots(figsize=(9, 4))
x = pd.to_datetime(serie.index, format="%Y%m")
ax.plot(x, serie.Planos, color="#2E75B6", lw=1.8, label="Planos de saúde (TISS/ANS)")
ax.plot(x, serie.SUS, color="#C00000", lw=1.8, label="SUS (SIH)")
for d, t in [("2021-04", "TUSS 30912296"), ("2022-11", "Portaria 3.904 (ITVA)"), ("2024-04", "Portaria 3.414")]:
    ax.axvline(pd.Timestamp(d), color="#777", ls=":", lw=1)
    ax.text(pd.Timestamp(d), ax.get_ylim()[1] * 0.97, " " + t, fontsize=7, va="top", color="#555")
ax.set_ylabel("TAVI por mês")
ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(0, 0.85))
ax.spines[["top", "right"]].set_visible(False)
fig.savefig(f"{S}/R3_serie_mensal_tavi.png", dpi=200, bbox_inches="tight")

# ---------- R4 ----------
linhas = []
for uf in sorted(UF_IBGE.values()):
    d = den.loc[uf]
    s = tavi[(tavi.ano == 2025) & tavi.uf_res.eq(uf)].groupby("faixa").size()
    p = tt[(tt.ano == 2025) & tt.uf_res.eq(uf)].groupby("faixa").size()
    a, c = dsr(s, d.sem_plano), dsr(p, d.benef)
    linhas.append({"uf": uf, "SUS_n": int(s.reindex(FAIXAS).fillna(0).sum()), "SUS_pm": round(a[0], 1),
                   "SUS_ic95": f"{a[1]:.1f}–{a[2]:.1f}", "Planos_n": int(p.reindex(FAIXAS).fillna(0).sum()),
                   "Planos_pm": round(c[0], 1), "Planos_ic95": f"{c[1]:.1f}–{c[2]:.1f}",
                   "pop60_sem_plano": float(d.sem_plano.sum()), "benef60": float(d.benef.sum())})
uft = pd.DataFrame(linhas).set_index("uf")
uft.to_csv(f"{S}/R4_taxas_uf_ic95.csv")


def gini(v, w):
    o = np.argsort(v)
    v, w = np.asarray(v)[o], np.asarray(w)[o] / np.sum(w)
    cw = np.cumsum(w)
    cv = np.cumsum(v * w) / np.sum(v * w)
    return 1 - np.sum(w * (cv + np.concatenate([[0], cv[:-1]])))


def theil(v, w):
    w = np.asarray(w) / np.sum(w)
    m = np.sum(w * v)
    r = np.asarray(v) / m
    return float(np.sum(w * np.where(r > 0, r * np.log(np.where(r > 0, r, 1)), 0)))


saida["R4"] = {
    "Gini_SUS": round(gini(uft.SUS_pm, uft.pop60_sem_plano), 3),
    "Gini_Planos": round(gini(uft.Planos_pm, uft.benef60), 3),
    "Theil_SUS": round(theil(uft.SUS_pm, uft.pop60_sem_plano), 3),
    "Theil_Planos": round(theil(uft.Planos_pm, uft.benef60), 3),
    "UFs_SUS_zero": int((uft.SUS_n == 0).sum()), "UFs_SUS_lt1": int((uft.SUS_pm < 1).sum()),
    "UFs_SUS_lt5": int((uft.SUS_pm < 5).sum()),
    "pct_pop60_sem_plano_em_UF_SUS_zero": round(100 * uft.pop60_sem_plano[uft.SUS_n == 0].sum() / uft.pop60_sem_plano.sum(), 1),
    "pct_pop60_sem_plano_em_UF_SUS_lt1": round(100 * uft.pop60_sem_plano[uft.SUS_pm < 1].sum() / uft.pop60_sem_plano.sum(), 1),
    "pct_pop60_sem_plano_em_UF_SUS_lt5": round(100 * uft.pop60_sem_plano[uft.SUS_pm < 5].sum() / uft.pop60_sem_plano.sum(), 1),
}

# ---------- R5 ----------
cache = json.load(open("tavi_savr/dados_ref/cnes_hospitais.json"))
prim = tavi.groupby("CNES").mes.min()
vol = tavi[tavi.ano.isin([2024, 2025])].groupby("CNES").size()
r5 = pd.DataFrame({"CNES": HABILITADOS})
r5["nome"] = r5.CNES.map(lambda c: (cache.get(c) or {}).get("nome_fantasia"))
r5["uf"] = r5.CNES.map(lambda c: UF_IBGE.get(str((cache.get(c) or {}).get("codigo_uf", ""))))
r5["primeiro_tavi"] = r5.CNES.map(prim)
r5["tavi_2024_2025"] = r5.CNES.map(vol).fillna(0).astype(int)
ini = pd.Period("2024-05", "M")
r5["meses_ate_primeiro"] = r5.primeiro_tavi.map(lambda m: (pd.Period(f"{m[:4]}-{m[4:]}", "M") - ini).n if isinstance(m, str) else np.nan)
r5.to_csv(f"{S}/R5_implantacao_habilitados.csv", index=False)
saida["R5"] = {f"pct_com_TAVI_ate_{k}m": round(100 * (r5.meses_ate_primeiro <= k).mean(), 1) for k in (6, 12, 18)}
saida["R5"]["sem_nenhuma_TAVI_ate_ago2026"] = int(r5.primeiro_tavi.isna().sum())
saida["R5"]["ja_operavam_antes_mai2024"] = int((r5.meses_ate_primeiro < 0).sum())

# ---------- R6 ----------
mun = pd.read_csv("tavi_savr/dados_ref/municipios_coordenadas.csv", dtype={"codigo_ibge": str})
mun["cod6"] = mun.codigo_ibge.str[:6]
coord = mun.set_index("cod6")[["latitude", "longitude"]]
ativos = vol[vol >= 10].index
# localização do hospital aproximada pelo centróide do seu município (como a residência), sem coordenada do estabelecimento
cent = pd.DataFrame({c: coord.loc[str(cache[c]["codigo_municipio"])[:6], ["latitude", "longitude"]].values
                     for c in ativos if c in cache}, index=["lat", "lon"]).T.astype(float)


def dist_min(cods):
    xy = coord.reindex(cods)
    la1, lo1 = np.radians(xy.latitude.values)[:, None], np.radians(xy.longitude.values)[:, None]
    la2, lo2 = np.radians(cent.lat.values)[None, :], np.radians(cent.lon.values)[None, :]
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return (6371 * 2 * np.arcsin(np.sqrt(h))).min(axis=1)


sp = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=["SP_NAIH", "SP_PROCREA", "SP_ATOPROF"])
                for f in glob.glob("saida_tavi/sp/parciais/SP*.csv*") if os.path.getsize(f) > 0]).apply(lambda s: s.str.strip())
mult = set(sp.loc[sp.SP_PROCREA.isin(["0415010012", "0415020034"]) & sp.SP_ATOPROF.eq("0406010692"), "SP_NAIH"])
aort = rd.DIAG_PRINC.str.match(r"^(I35|I06|Q23[01])")
savr = rd[rd.IDENT.eq("1") & aort & rd.ano.isin([2024, 2025]) & (rd.idade >= 70) &
          (rd.PROC_REA.eq("0406010692") | (rd.PROC_REA.isin(["0415010012", "0415020034"]) & rd.N_AIH.isin(mult)))].copy()
grupos = {"SAVR aórtica ≥70 (SUS)": savr, "TAVI (SUS)": tavi[tavi.ano.isin([2024, 2025])].copy()}
lin = []
for g, d in grupos.items():
    d = d.assign(dist=dist_min(d.MUNIC_RES.values), regiao=d.MUNIC_RES.str[:1].map(REGIAO))
    for reg, x in list(d.groupby("regiao")) + [("Brasil", d)]:
        lin.append({"grupo": g, "regiao": reg, "n": len(x), "mediana_km": round(x.dist.median(), 0),
                    "p75_km": round(x.dist.quantile(.75), 0), "pct_mais_100km": round(100 * (x.dist > 100).mean(), 1),
                    "pct_mais_300km": round(100 * (x.dist > 300).mean(), 1)})
pd.DataFrame(lin).to_csv(f"{S}/R6_distancia_centro_tavi_mais_proximo.csv", index=False)
saida["R6_centros_ativos"] = len(cent)

# ---------- R7 ----------
t7 = tavi.assign(faixa5=pd.cut(tavi.idade, [0, 59.99, 64.99, 69.99, 74.99, 79.99, 200],
                               labels=["<60", "60-64", "65-69", "70-74", "75-79", "≥80"]).astype(str),
                 periodo=np.where(tavi.mes < "202405", "antes de mai/2024", "mai/2024 em diante"))
t7.pivot_table(index=["PROC_REA", "periodo"], columns="faixa5", values="N_AIH", aggfunc="size", fill_value=0).to_csv(
    f"{S}/R7_tavi_idade_codigo_periodo.csv")
saida["R7"] = {"menos75": int((tavi.idade < 75).sum()), "total": len(tavi),
               "menos75_antes_mai2024": int(((tavi.idade < 75) & (tavi.mes < "202405")).sum()),
               "menos75_urgencia": int(((tavi.idade < 75) & tavi.CAR_INT.ne("01")).sum())}

json.dump(saida, open(f"{S}/resultados_v2.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(saida, ensure_ascii=False, indent=1))
print(pd.read_csv(f"{S}/R6_distancia_centro_tavi_mais_proximo.csv").to_string())
print(r5.sort_values("meses_ate_primeiro").to_string())
print(pd.read_csv(f"{S}/R7_tavi_idade_codigo_periodo.csv").to_string())
