#!/usr/bin/env python3
"""Auditorias pedidas na segunda opinião (31/out/2026). Lê as saídas de nacional_sus_ans.py e os extratos.

A1  AIH de cirurgias múltiplas/sequenciais com troca valvar (SUS), por CID principal; nas de CID aórtico, o que mais
    foi feito na mesma AIH (SIH-SP), por ano.
A2  Denominadores: taxas por milhão com população total, beneficiários e população sem plano; padronização direta por
    idade (população brasileira de 2022, faixas 60–69/70–79/≥80) para comparar SUS-dependentes × beneficiários.
A3  Valva aórtica no TISS: limites inferior (só CID aórtico explícito), central (imputado) e superior (todo evento sem
    CID valvar contado como aórtico) e efeito na comparação SUS × planos.
A4  TAVI SUS <75 anos por período e hospital.
Saída: tavi_savr/resultados_auditoria/.
"""
import glob
import os

import numpy as np
import pandas as pd

R = "tavi_savr/resultados_nacional"
S = "tavi_savr/resultados_auditoria"
os.makedirs(S, exist_ok=True)
FAIXAS = ["60-69", "70-79", "80+"]

# ---------- A1 ----------
GRUPOS_ATO = {
    "CRVM": ["0406010927", "0406010935", "0406010943", "0406010951"],
    "Raiz da aorta / tubo valvado": ["0406010838", "0406010846"],
    "Aorta ascendente / arco / dissecção": ["0406010986", "0406010994", "0406010137"],
    "Plástica valvar (outra valva)": ["0406010803", "0406010811"],
    "Troca/plástica múltipla": ["0406010820"],
    "Ampliação VSVE / anel": ["0406010056", "0406011290"],
    "Assistência circulatória": ["0406010714"],
}
sp = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False,
                            usecols=["SP_NAIH", "SP_PROCREA", "SP_ATOPROF", "SP_DTINTER", "SP_CIDPRI"])
                for f in sorted(glob.glob("saida_tavi/sp/parciais/SP*.csv*")) if os.path.getsize(f) > 0],
               ignore_index=True).apply(lambda s: s.str.strip())
mult = sp[sp["SP_PROCREA"].isin(["0415010012", "0415020034"])]
com_troca = set(mult.loc[mult["SP_ATOPROF"].eq("0406010692"), "SP_NAIH"])
m = mult[mult["SP_NAIH"].isin(com_troca)].drop_duplicates(["SP_NAIH", "SP_ATOPROF"])
aih = m.groupby("SP_NAIH").agg(ano=("SP_DTINTER", lambda s: s.iloc[0][:4]), atos=("SP_ATOPROF", set),
                               cid=("SP_CIDPRI", "first"))
# o SIH-SP traz AIH múltiplas com troca valvar de qualquer valva; separar pelo CID principal
aih["cid_grupo"] = np.select([aih["cid"].str.match(r"^(I35|I06|Q23[01])"), aih["cid"].str.startswith("I71"),
                              aih["cid"].str.match(r"^(I05|I34)")],
                             ["aórtico (I35/I06/Q230-1)", "aneurisma/dissecção de aorta (I71)", "mitral (I05/I34)"],
                             "outro")
aih[aih["ano"].between("2010", "2025")].pivot_table(index="ano", columns="cid_grupo", values="cid", aggfunc="size",
                                                   fill_value=0).to_csv(f"{S}/A1_multiplas_com_troca_por_cid.csv")
print(aih[aih["ano"].between("2015", "2025")].pivot_table(index="ano", columns="cid_grupo", values="cid",
                                                          aggfunc="size", fill_value=0).to_string())
aih = aih[aih["cid_grupo"].eq("aórtico (I35/I06/Q230-1)")]
for g, cods in GRUPOS_ATO.items():
    aih[g] = aih["atos"].apply(lambda a: bool(a & set(cods)))
aih["nenhum dos acima"] = ~aih[list(GRUPOS_ATO)].any(axis=1)
a1 = aih[aih["ano"].between("2010", "2025")].groupby("ano")[list(GRUPOS_ATO) + ["nenhum dos acima"]].sum()
a1.insert(0, "AIH com troca valvar", aih[aih["ano"].between("2010", "2025")].groupby("ano").size())
a1.to_csv(f"{S}/A1_multiplas_com_troca_por_ato_associado.csv")
print("A1\n", a1.loc["2015":].to_string())

# ---------- A2 e A3 ----------
t = pd.read_csv(f"{R}/nacional_ano_faixa.csv")
tv = pd.read_csv(f"{R}/ans_troca_valvar_imputacao.csv")
t = t.merge(tv[["ano", "faixa", "sem CID valvar"]], on=["ano", "faixa"], how="left")
t["SAVRaort_ANS_inferior"] = t["SAVRaort_ANS_cid"]
t["SAVRaort_ANS_central"] = t["SAVRaort_ANS_imput"]
t["SAVRaort_ANS_superior"] = t["SAVRaort_ANS_cid"] + t["sem CID valvar"]
# padrão: população brasileira 2022 nas faixas ≥60
padrao = t[(t.ano == 2022) & t.faixa.isin(FAIXAS)].set_index("faixa")["pop"]
w = padrao / padrao.sum()

linhas = []
for ano in range(2015, 2026):
    x = t[(t.ano == ano) & t.faixa.isin(FAIXAS)].set_index("faixa")
    r = {"ano": ano}
    for nome, num, den in [
        ("TAVI_SUS_por_sem_plano", "TAVI_SUS", "sus_dependentes"),
        ("TAVI_ANS_por_beneficiario", "TAVI_ANS", "beneficiarios"),
        ("TAVI_total_por_populacao", "TAVI_total", "pop"),
        ("TAVI_SUS_por_populacao_total", "TAVI_SUS", "pop"),
        ("SAVRaort_SUS_por_sem_plano", "SAVRaort_SUS", "sus_dependentes"),
        ("SAVRaort_ANS_inf_por_beneficiario", "SAVRaort_ANS_inferior", "beneficiarios"),
        ("SAVRaort_ANS_cent_por_beneficiario", "SAVRaort_ANS_central", "beneficiarios"),
        ("SAVRaort_ANS_sup_por_beneficiario", "SAVRaort_ANS_superior", "beneficiarios"),
    ]:
        taxa = 1e6 * x[num] / x[den]
        r[nome + "_padr60mais"] = round(float((taxa * w).sum()), 1)
    linhas.append(r)
a2 = pd.DataFrame(linhas).set_index("ano")
a2["razao_TAVI_planos_SUS_padr"] = (a2["TAVI_ANS_por_beneficiario_padr60mais"] /
                                    a2["TAVI_SUS_por_sem_plano_padr60mais"]).round(1)
for lim in ["inf", "cent", "sup"]:
    a2[f"razao_SAVR_planos_SUS_{lim}"] = (a2[f"SAVRaort_ANS_{lim}_por_beneficiario_padr60mais"] /
                                         a2["SAVRaort_SUS_por_sem_plano_padr60mais"]).round(2)
a2.to_csv(f"{S}/A2_A3_taxas_padronizadas_e_limites.csv")
print("A2/A3\n", a2.loc[2021:].T.to_string())

# % TAVI entre AVR aórtica por faixa, 2025, nos três limites
p = t[(t.ano == 2025) & t.faixa.isin(FAIXAS)].set_index("faixa")
a3 = pd.DataFrame({lim: (100 * p["TAVI_ANS"] / (p["TAVI_ANS"] + p[f"SAVRaort_ANS_{lim}"])).round(1)
                   for lim in ["inferior", "central", "superior"]})
a3["SUS"] = (100 * p["TAVI_SUS"] / (p["TAVI_SUS"] + p["SAVRaort_SUS"])).round(1)
a3.to_csv(f"{S}/A3_pct_TAVI_2025_limites.csv")
print("A3 % TAVI 2025\n", a3.to_string())

# taxas por faixa 2025 com os 3 denominadores (sem padronizar)
d = p[["TAVI_SUS", "TAVI_ANS", "pop", "beneficiarios", "sus_dependentes"]].copy()
d["TAVI_SUS_pm_pop_total"] = (1e6 * d.TAVI_SUS / d["pop"]).round(1)
d["TAVI_SUS_pm_sem_plano"] = (1e6 * d.TAVI_SUS / d.sus_dependentes).round(1)
d["TAVI_ANS_pm_benef"] = (1e6 * d.TAVI_ANS / d.beneficiarios).round(1)
d["cobertura_planos_pct"] = (100 * d.beneficiarios / d["pop"]).round(1)
d.to_csv(f"{S}/A2_tres_denominadores_2025.csv")
print(d.to_string())

# ---------- A4 ----------
rd = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False,
                            usecols=["PROC_REA", "IDENT", "IDADE", "COD_IDADE", "DT_INTER", "CNES", "CAR_INT"])
                for f in glob.glob("saida_tavi/parciais/RD*.csv*") if os.path.getsize(f) > 0]).apply(lambda s: s.str.strip())
tv_ = rd[rd.PROC_REA.isin(["0406030162", "0406011524"]) & rd.IDENT.eq("1")].copy()
i = pd.to_numeric(tv_.IDADE, errors="coerce")
tv_["idade"] = np.where(tv_.COD_IDADE.eq("4"), i, np.where(tv_.COD_IDADE.eq("5"), 100 + i, np.nan))
tv_["lt75"] = tv_.idade < 75
tv_["semestre"] = tv_.DT_INTER.str[:4] + "S" + np.where(tv_.DT_INTER.str[4:6].astype(int) <= 6, "1", "2")
tv_.groupby(["PROC_REA", "semestre"]).agg(n=("lt75", "size"), menos75=("lt75", "sum")).to_csv(f"{S}/A4_tavi_lt75_semestre.csv")
h = tv_.groupby("CNES").agg(n=("lt75", "size"), menos75=("lt75", "sum"), idade_mediana=("idade", "median"))
h["pct_menos75"] = (100 * h.menos75 / h.n).round(1)
h.sort_values("n", ascending=False).to_csv(f"{S}/A4_tavi_lt75_hospital.csv")
top4 = h.sort_values("menos75", ascending=False).head(4)
print("A4: 4 hospitais concentram", int(top4.menos75.sum()), "de", int(h.menos75.sum()), "TAVI <75")
