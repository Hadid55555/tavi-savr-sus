#!/usr/bin/env python3
"""Modelo ecológico por UF (2025, ≥60 anos) e decomposição SUS × planos.

Desfecho: TAVI SUS por UF de residência (contagem). Offset: log do número esperado por padronização indireta (taxas
nacionais do SUS por faixa 60–69/70–79/≥80 × população sem plano da UF na faixa). Binomial negativa (NB2, statsmodels);
sensibilidade Poisson com erro-padrão robusto. Covariáveis (n = 27, poucas de propósito): cobertura de planos ≥60 (por 10
pontos), centro SUS ativo na UF (≥1 TAVI SUS em 2024–25 em hospital da UF), óbitos com causa básica I35 em ≥70 anos por
100 mil (2023–25, carga). Mesmo modelo para SAVR aórtica SUS e TAVI planos (contraste).
Decomposição: diferença bruta × padronizada (≥60) da taxa de TAVI planos − SUS → parte devida à estrutura etária.
Saída: tavi_savr/resultados_modelo_uf/.
"""
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
S = "tavi_savr/resultados_modelo_uf"
os.makedirs(S, exist_ok=True)
F = ["60-69", "70-79", "80+"]
pop = pd.read_csv("artigo/dados_ref/populacao_uf_ano_faixa.csv")
pop25 = pop[(pop.ano == 2025) & pop.faixa.isin(F)].set_index(["uf", "faixa"])["pop"]
b = pd.read_csv("ciha/dados_ref/ans_beneficiarios_medicos_dezembro_uf.csv", dtype={"CD_FAIXA_E": str})
b = b[(b.ano == 2025) & b.CD_FAIXA_E.ne("99")]
cf = b.CD_FAIXA_E.astype(int)
b["faixa"] = np.select([cf >= 26, cf >= 24, cf >= 22], ["80+", "70-79", "60-69"], "<60")
ben = b[b.faixa.isin(F)].groupby(["SG_UF", "faixa"]).NR_BENEF_M.sum()
ben.index.names = ["uf", "faixa"]
den = pd.DataFrame({"pop": pop25, "benef": ben}).fillna(0)
den["sem_plano"] = den["pop"] - den["benef"]

# taxas nacionais por faixa (2025) de resultados_nacional
nac = pd.read_csv("tavi_savr/resultados_nacional/nacional_ano_faixa.csv")
nac = nac[(nac.ano == 2025) & nac.faixa.isin(F)].set_index("faixa")
taxa = {"TAVI_SUS": nac.TAVI_SUS / nac.sus_dependentes, "SAVR_SUS": nac.SAVRaort_SUS / nac.sus_dependentes,
        "TAVI_Planos": nac.TAVI_ANS / nac.beneficiarios}
dcol = {"TAVI_SUS": "sem_plano", "SAVR_SUS": "sem_plano", "TAVI_Planos": "benef"}

uf = pd.read_csv("tavi_savr/resultados_geografia/taxas_uf_residencia_2025_padronizadas.csv").set_index("uf")
hosp = pd.read_csv("tavi_savr/resultados_geografia/hospitais_por_uf.csv").set_index("uf")
ix = pd.read_csv("tavi_savr/resultados_carga_capacidade/indice_AVR_por_obito_I35_uf_2023_2025.csv").set_index("uf")
cnes = pd.read_csv("tavi_savr/resultados_carga_capacidade/CNES_habilitacoes_cardio_uf_set2026.csv").set_index("uf")
pop70 = pop[(pop.ano.isin([2023, 2024, 2025])) & pop.faixa.isin(["70-79", "80+"])].groupby("uf")["pop"].sum()

d = pd.DataFrame(index=sorted(uf.index))
d["TAVI_SUS"] = uf["TAVI_SUS_n"]
d["SAVR_SUS"] = uf["SAVR aórtica_SUS_n"]
d["TAVI_Planos"] = uf["TAVI_Planos_n"]
for k in taxa:
    d[f"esp_{k}"] = [sum(taxa[k][f] * den.loc[(u, f), dcol[k]] for f in F) for u in d.index]
d["cobertura_10pp"] = uf["cobertura_planos_60mais_pct"] / 10
d["centro_SUS_ativo"] = (hosp["hosp_TAVI"] > 0).astype(int).reindex(d.index).fillna(0)
d["hab_0815"] = (cnes["TAVI (08.15)"] > 0).astype(int).reindex(d.index).fillna(0)
d["obitos_I35_70mais_100mil"] = 1e5 * ix["obitos_I35_basica_70mais"].reindex(d.index) / pop70.reindex(d.index)
d["pop60_sem_plano"] = [den.loc[u, "sem_plano"].sum() for u in d.index]
d.round(3).to_csv(f"{S}/dados_modelo_uf.csv")

linhas = []
X = ["cobertura_10pp", "centro_SUS_ativo", "obitos_I35_70mais_100mil"]
for y in ["TAVI_SUS", "SAVR_SUS", "TAVI_Planos"]:
    xs = X if y != "TAVI_Planos" else ["cobertura_10pp", "obitos_I35_70mais_100mil"]
    Xm = sm.add_constant(d[xs].astype(float))
    off = np.log(d[f"esp_{y}"].astype(float))
    for nome, mod in [("NB2", sm.NegativeBinomial(d[y].astype(float), Xm, offset=off)),
                      ("Poisson robusto", sm.GLM(d[y].astype(float), Xm, family=sm.families.Poisson(), offset=off))]:
        r = mod.fit(disp=0, maxiter=500) if nome == "NB2" else mod.fit(cov_type="HC1")
        ci = r.conf_int()
        for v in xs:
            linhas.append({"desfecho": y, "modelo": nome, "variavel": v, "IRR": np.exp(r.params[v]),
                           "IC95_inf": np.exp(ci.loc[v, 0]), "IC95_sup": np.exp(ci.loc[v, 1]), "p": r.pvalues[v]})
        if nome == "NB2":
            linhas.append({"desfecho": y, "modelo": nome, "variavel": "alpha (sobredispersão)",
                           "IRR": r.params["alpha"], "IC95_inf": ci.loc["alpha", 0], "IC95_sup": ci.loc["alpha", 1],
                           "p": r.pvalues["alpha"]})
m = pd.DataFrame(linhas)
m[["IRR", "IC95_inf", "IC95_sup"]] = m[["IRR", "IC95_inf", "IC95_sup"]].round(2)
m["p"] = m.p.round(4)
m.to_csv(f"{S}/modelo_uf_irr.csv", index=False)
print(m.to_string())

# correlações simples (Spearman) como descrição
cor = d[["TAVI_SUS", "SAVR_SUS"]].div(d[["esp_TAVI_SUS", "esp_SAVR_SUS"]].values).rename(columns=lambda c: c + "_O/E")
cor["obitos"] = d["obitos_I35_70mais_100mil"]
cor["cobertura"] = d["cobertura_10pp"] * 10
print(cor.corr(method="spearman").round(2))
cor.round(2).to_csv(f"{S}/razao_observado_esperado_uf.csv")

# decomposição
padrao = pop[(pop.ano == 2022) & pop.faixa.isin(F)].groupby("faixa")["pop"].sum()
w = padrao / padrao.sum()
sus_r = nac.TAVI_SUS / nac.sus_dependentes * 1e6
pl_r = nac.TAVI_ANS / nac.beneficiarios * 1e6
bruta_sus = 1e6 * nac.TAVI_SUS.sum() / nac.sus_dependentes.sum()
bruta_pl = 1e6 * nac.TAVI_ANS.sum() / nac.beneficiarios.sum()
pad_sus, pad_pl = (sus_r * w).sum(), (pl_r * w).sum()
dec = pd.DataFrame([{"SUS_bruta": bruta_sus, "Planos_bruta": bruta_pl, "razao_bruta": bruta_pl / bruta_sus,
                     "SUS_padronizada": pad_sus, "Planos_padronizada": pad_pl, "razao_padronizada": pad_pl / pad_sus,
                     "pct_80mais_sem_plano": 100 * nac.sus_dependentes["80+"] / nac.sus_dependentes.sum(),
                     "pct_80mais_benef": 100 * nac.beneficiarios["80+"] / nac.beneficiarios.sum(),
                     "pct_diferenca_bruta_devida_idade": 100 * (1 - (pad_pl - pad_sus) / (bruta_pl - bruta_sus))}]).round(2)
dec.to_csv(f"{S}/decomposicao_sus_planos_2025.csv", index=False)
print(dec.T)

# ---------- estabilidade: retirar uma UF de cada vez (TAVI SUS, NB2) ----------
loo = []
for u in d.index:
    dd = d.drop(index=u)
    Xm = sm.add_constant(dd[X].astype(float))
    try:
        r = sm.NegativeBinomial(dd["TAVI_SUS"].astype(float), Xm, offset=np.log(dd["esp_TAVI_SUS"].astype(float))).fit(disp=0, maxiter=500)
        loo.append({"uf_retirada": u, **{f"IRR_{v}": np.exp(r.params[v]) for v in X}})
    except Exception as e:
        loo.append({"uf_retirada": u, "erro": str(e)[:60]})
loo = pd.DataFrame(loo).round(2)
loo.to_csv(f"{S}/modelo_uf_retirando_uma_uf.csv", index=False)
print(loo.describe().loc[["min", "max"]])
