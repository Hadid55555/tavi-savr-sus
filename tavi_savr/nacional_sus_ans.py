#!/usr/bin/env python3
"""Série nacional TAVI × troca valvar, SUS (SIH) + saúde suplementar (TISS/ANS), 2015–2025, por faixa etária.

Definições harmonizadas (um evento = uma internação; ano = ano da internação no SIH, ANO_MES_EVENTO no TISS):
  TAVI           SUS: PROC_REA 0406011524/0406030162.  ANS: TUSS 30912296 no evento.
  Troca valvar   SUS: PROC_REA 0406010692, ou AIH de cirurgias múltiplas/sequenciais (0415010012/0415020034) cujo
  (uma valva)         SIH-SP tem o ato 0406010692.  ANS: TUSS 30902053 no evento, sem 30912296/30903033/30902029.
    ...aórtica   SUS: CID principal I35/I06/Q230/Q231.  ANS: algum CID_1–4 aórtico; evento sem CID → imputado pela
                 fração aórtica entre os com CID valvar conhecido no mesmo ano × faixa (sensibilidade: sem imputar).
  Combinadas     SUS: 0406011206 (troca + CRVM), 0406010820 (múltipla).  ANS: 30903033, 30902029.
Faixas comuns (o TISS só tem faixas de 10 anos): <60, 60–69, 70–79, ≥80.
Óbito: SUS MORTE = 1; ANS motivo de saída 41–43.
Denominadores: IBGE projeção rev. 2018 (artigo/dados_ref/proj7358.json); beneficiários de plano médico-hospitalar em
dezembro (ANS, ciha/dados_ref/ans_beneficiarios_medicos_dezembro_uf.csv); SUS-dependentes = população − beneficiários.
Saída: tavi_savr/resultados_nacional/.
"""
import glob
import json
import os

import numpy as np
import pandas as pd

SAIDA = "tavi_savr/resultados_nacional"
os.makedirs(SAIDA, exist_ok=True)
FAIXAS = ["<60", "60-69", "70-79", "80+"]
ANOS = range(2015, 2026)
AORT = r"^(I35|I06|Q23[01])"


def faixa_idade(a):
    return pd.cut(a, [-1, 59.999, 69.999, 79.999, 200], labels=FAIXAS).astype(str)


# ---------- SUS ----------
rd = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in sorted(glob.glob("saida_tavi/parciais/RD*.csv*"))
                if os.path.getsize(f) > 0], ignore_index=True)
rd = rd[rd["IDENT"].str.strip().eq("1")].copy()
for c in ["PROC_REA", "DIAG_PRINC", "N_AIH", "CNES", "COD_IDADE", "IDADE", "MORTE", "DT_INTER"]:
    rd[c] = rd[c].str.strip()
i = pd.to_numeric(rd["IDADE"], errors="coerce")
rd["idade"] = np.where(rd["COD_IDADE"].eq("4"), i, np.where(rd["COD_IDADE"].eq("5"), 100 + i, np.where(
    rd["COD_IDADE"].isin(["2", "3"]), 0, np.nan)))
rd["ano"] = pd.to_datetime(rd["DT_INTER"], format="%Y%m%d", errors="coerce").dt.year
rd["obito"] = pd.to_numeric(rd["MORTE"], errors="coerce").fillna(0).astype(int)
rd["aortico"] = rd["DIAG_PRINC"].str.match(AORT)

sp = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=["SP_NAIH", "SP_CNES", "SP_PROCREA", "SP_ATOPROF"])
                for f in sorted(glob.glob("saida_tavi/sp/parciais/SP*.csv*")) if os.path.getsize(f) > 0], ignore_index=True)
sp = sp.apply(lambda s: s.str.strip())
mult_com_troca = set(sp.loc[sp["SP_PROCREA"].isin(["0415010012", "0415020034"]) & sp["SP_ATOPROF"].eq("0406010692"),
                            "SP_NAIH"])

p = rd["PROC_REA"]
rd["grupo"] = np.select(
    [p.isin(["0406011524", "0406030162"]),
     p.eq("0406010692"),
     p.isin(["0415010012", "0415020034"]) & rd["N_AIH"].isin(mult_com_troca),
     p.isin(["0406011206", "0406010820"])],
    ["TAVI", "Troca valvar", "Troca valvar", "Combinadas"], "")
rd["via_multiplas"] = p.isin(["0415010012", "0415020034"]) & rd["grupo"].eq("Troca valvar")
sus = rd[rd["grupo"].ne("") & rd["ano"].isin(ANOS)].copy()
sus["faixa"] = faixa_idade(sus["idade"])
sus["fonte"] = "SUS"
# a AIH de cirurgias múltiplas só entrou se teve CID aórtico (filtro da extração RD); as de outras valvas ficam de fora
sus["valva"] = np.where(sus["aortico"], "aórtica", "outra/indeterminada")

# ---------- ANS (TISS) ----------
tiss = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in sorted(glob.glob("saida_tavi/tiss/parciais/*.csv*"))
                  if os.path.getsize(f) > 0], ignore_index=True)
tiss = tiss.drop_duplicates("ID_EVENTO_ATENCAO_SAUDE")
c = tiss["cods_tuss"]
tiss["grupo"] = np.select(
    [c.str.contains("30912296"), c.str.contains("30903033|30902029"), c.str.contains("30902053")],
    ["TAVI", "Combinadas", "Troca valvar"], "")
tiss["ano"] = pd.to_numeric(tiss["ANO_MES_EVENTO"].str[:4], errors="coerce")
fx = tiss["FAIXA_ETARIA"].str.extract(r"^(\d+)")[0].astype(float)
tiss["faixa"] = np.select([fx >= 80, fx >= 70, fx >= 60, fx.notna()], ["80+", "70-79", "60-69", "<60"], "ignorada")
tiss.loc[tiss["FAIXA_ETARIA"].str.contains("menos de 1|< 1", case=False, regex=True), "faixa"] = "<60"
tiss["obito"] = tiss["CD_MOTIVO_SAIDA"].str.strip().isin(["41", "42", "43"]).astype(int)
cids = tiss[["CID_1", "CID_2", "CID_3", "CID_4"]].apply(lambda s: s.str.strip().str.upper())
aort = cids.apply(lambda s: s.str.match(AORT)).any(axis=1)
outra_valva = cids.apply(lambda s: s.str.match(r"^(I34|I05|I36|I37|I07|I08|I09|Q22|Q232|Q233)")).any(axis=1)
tiss["valva"] = np.select([aort, outra_valva], ["aórtica", "outra"], "sem CID valvar")
ans = tiss[tiss["grupo"].ne("") & tiss["ano"].isin(ANOS)].copy()
ans["fonte"] = "ANS"

# ---------- contagens ----------
cols = ["fonte", "grupo", "ano", "faixa", "valva", "obito"]
ev = pd.concat([sus[cols], ans[cols]], ignore_index=True)
cont = ev.groupby(["fonte", "grupo", "ano", "faixa", "valva"]).agg(n=("obito", "size"), obitos=("obito", "sum")).reset_index()
cont.to_csv(f"{SAIDA}/eventos_fonte_grupo_ano_faixa_valva.csv", index=False)

# troca valvar aórtica no ANS com imputação dos sem CID valvar
tv = cont[(cont.fonte == "ANS") & (cont.grupo == "Troca valvar")].pivot_table(
    index=["ano", "faixa"], columns="valva", values="n", aggfunc="sum", fill_value=0)
for k in ["aórtica", "outra", "sem CID valvar"]:
    if k not in tv:
        tv[k] = 0
fr_ano = tv.groupby(level="ano")[["aórtica", "outra"]].sum()
fr_ano = fr_ano["aórtica"] / (fr_ano["aórtica"] + fr_ano["outra"])
frac = (tv["aórtica"] / (tv["aórtica"] + tv["outra"])).where(lambda s: (tv["aórtica"] + tv["outra"]) >= 20)
frac = frac.fillna(pd.Series(tv.index.get_level_values("ano").map(fr_ano), index=tv.index))
tv["frac_aortica_conhecida"] = frac.round(3)
tv["aortica_imputada"] = (tv["aórtica"] + frac * tv["sem CID valvar"]).round(0)
tv.to_csv(f"{SAIDA}/ans_troca_valvar_imputacao.csv")

# ---------- denominadores ----------
p = pd.DataFrame(json.load(open("artigo/dados_ref/proj7358.json"))[1:])
p["V"] = pd.to_numeric(p["V"], errors="coerce")
p["ano"] = p["D6N"].astype(int)
mapa = {"60 a 64 anos": "60-69", "65 a 69 anos": "60-69", "70 a 74 anos": "70-79", "75 a 79 anos": "70-79",
        "80 anos ou mais": "80+"}
p = p[~p["D5N"].isin(["80 a 84 anos", "85 a 89 anos", "90 anos ou mais"])]
p["faixa"] = p["D5N"].map(mapa).fillna("<60")
pop = p.groupby(["ano", "faixa"])["V"].sum().rename("pop")
b = pd.read_csv("ciha/dados_ref/ans_beneficiarios_medicos_dezembro_uf.csv", dtype={"CD_FAIXA_E": str})
b = b[b["CD_FAIXA_E"].ne("99")]
cf = b["CD_FAIXA_E"].astype(int)
b["faixa"] = np.select([cf >= 26, cf >= 24, cf >= 22], ["80+", "70-79", "60-69"], "<60")
ben = b.groupby(["ano", "faixa"])["NR_BENEF_M"].sum().rename("beneficiarios")
den = pd.concat([pop, ben], axis=1).reset_index()
den["sus_dependentes"] = den["pop"] - den["beneficiarios"]
den.to_csv(f"{SAIDA}/denominadores_ano_faixa.csv", index=False)

# ---------- tabela principal: por ano × faixa ----------
def n(fonte, grupo, aortica=False):
    s = cont[(cont.fonte == fonte) & (cont.grupo == grupo)]
    if aortica:
        s = s[s.valva == "aórtica"]
    return s.groupby(["ano", "faixa"])["n"].sum()


t = pd.DataFrame({
    "TAVI_SUS": n("SUS", "TAVI"), "TAVI_ANS": n("ANS", "TAVI"),
    "TrocaValvar_SUS": n("SUS", "Troca valvar"), "TrocaValvar_ANS": n("ANS", "Troca valvar"),
    "SAVRaort_SUS": n("SUS", "Troca valvar", True), "SAVRaort_ANS_cid": n("ANS", "Troca valvar", True),
    "SAVRaort_ANS_imput": tv["aortica_imputada"],
}).fillna(0).reset_index()
t = t[t["faixa"].isin(FAIXAS)].merge(den, on=["ano", "faixa"], how="left")
t["TAVI_total"] = t.TAVI_SUS + t.TAVI_ANS
t["SAVRaort_total"] = t.SAVRaort_SUS + t.SAVRaort_ANS_imput
t["TAVI_pm"] = (1e6 * t.TAVI_total / t["pop"]).round(1)
t["SAVRaort_pm"] = (1e6 * t.SAVRaort_total / t["pop"]).round(1)
t["TAVI_SUS_pm_dep"] = (1e6 * t.TAVI_SUS / t.sus_dependentes).round(1)
t["TAVI_ANS_pm_benef"] = (1e6 * t.TAVI_ANS / t.beneficiarios).round(1)
t["SAVRaort_SUS_pm_dep"] = (1e6 * t.SAVRaort_SUS / t.sus_dependentes).round(1)
t["SAVRaort_ANS_pm_benef"] = (1e6 * t.SAVRaort_ANS_imput / t.beneficiarios).round(1)
t["pct_TAVI_total"] = (100 * t.TAVI_total / (t.TAVI_total + t.SAVRaort_total)).round(1)
t["pct_TAVI_SUS"] = (100 * t.TAVI_SUS / (t.TAVI_SUS + t.SAVRaort_SUS)).round(1)
t["pct_TAVI_ANS"] = (100 * t.TAVI_ANS / (t.TAVI_ANS + t.SAVRaort_ANS_imput)).round(1)
t.to_csv(f"{SAIDA}/nacional_ano_faixa.csv", index=False)

# distribuição etária da TAVI e da SAVR aórtica por fonte e ano
dist = ev[ev.grupo.eq("TAVI") | (ev.grupo.eq("Troca valvar") & ev.valva.eq("aórtica"))].pivot_table(
    index=["grupo", "fonte", "ano"], columns="faixa", values="obito", aggfunc="size", fill_value=0)
dist = dist.div(dist.sum(axis=1), axis=0).mul(100).round(1).join(dist.sum(axis=1).rename("n"))
dist.to_csv(f"{SAIDA}/distribuicao_etaria_pct.csv")

# mortalidade hospitalar bruta por fonte × grupo × faixa (2024–2025)
mort = ev[ev.ano.isin([2024, 2025]) & ev.faixa.isin(FAIXAS)].groupby(["grupo", "fonte", "faixa"]).agg(
    n=("obito", "size"), obitos=("obito", "sum"))
mort["mort_pct"] = (100 * mort.obitos / mort.n).round(1)
mort.to_csv(f"{SAIDA}/mortalidade_2024_2025.csv")

# completude do TISS: eventos por ano e por mil beneficiários
cob = [json.loads(l) for l in open("saida_tavi/tiss/parciais/_cobertura.jsonl")]
cob = pd.DataFrame(cob).drop_duplicates("arquivo", keep="last")
comp = cob.groupby("ano").agg(arquivos_lidos=("status", lambda s: (s == "lido").sum()),
                              arquivos_ausentes=("status", lambda s: (s == "ausente").sum()),
                              arquivos_falha=("status", lambda s: (s == "falhou").sum()),
                              eventos_hosp=("cons_linhas", "sum"), ids_duplicados=("cons_ids_duplicados", "sum"),
                              cid1_preenchido=("cid1_preenchido", "sum"))
comp["beneficiarios"] = ben.groupby("ano").sum().reindex(comp.index)
comp["eventos_por_mil_benef"] = (1e3 * comp.eventos_hosp / comp.beneficiarios).round(1)
comp["pct_cid1"] = (100 * comp.cid1_preenchido / comp.eventos_hosp).round(1)
comp.to_csv(f"{SAIDA}/tiss_completude_ano.csv")

print(comp.to_string())
pd.set_option("display.width", 250)
print(t.groupby("ano")[["TAVI_SUS", "TAVI_ANS", "SAVRaort_SUS", "SAVRaort_ANS_cid", "SAVRaort_ANS_imput",
                        "TrocaValvar_SUS", "TrocaValvar_ANS"]].sum().to_string())
print(t[t.ano.isin([2019, 2022, 2024, 2025])][["ano", "faixa", "TAVI_SUS", "TAVI_ANS", "SAVRaort_SUS",
                                                 "SAVRaort_ANS_imput", "TAVI_pm", "SAVRaort_pm", "pct_TAVI_total",
                                                 "pct_TAVI_SUS", "pct_TAVI_ANS"]].to_string())
print(dist.to_string())
print(mort.to_string())
print("AIH de cirurgias múltiplas com troca valvar (SUS):", int(sus["via_multiplas"].sum()))
