#!/usr/bin/env python3
"""Geografia e hospitais: TAVI e SAVR aórtica por UF de residência (SUS × planos), deslocamento e centros.

- Taxas por UF de residência, 2025, pacientes ≥60 anos, padronizadas por idade (população brasileira de 2022, faixas
  60–69/70–79/≥80): SUS por milhão de habitantes sem plano; planos por milhão de beneficiários.
- Deslocamento: distância em linha reta (haversine) entre o município de residência e o do hospital; % tratados fora da
  UF de residência. Coordenadas municipais: kelvins/municipios-brasileiros (tavi_savr/dados_ref/municipios_coordenadas.csv).
- Hospitais SUS: nome e coordenadas pela API de dados abertos do CNES (cache em tavi_savr/dados_ref/cnes_hospitais.json);
  produção de TAVI e SAVR aórtica 2024–2025; hospitais com SAVR e sem TAVI.
- Mapa: tavi_savr/resultados_geografia/mapa_tavi_uf_2025.png (malha: click_that_hood/brazil-states.geojson).
Lê os extratos de saida_tavi/ (RD, SP, TISS). Saída: tavi_savr/resultados_geografia/.
"""
import glob
import json
import os
import time
import urllib.request

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import PatchCollection  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

S = "tavi_savr/resultados_geografia"
os.makedirs(S, exist_ok=True)
REF = "tavi_savr/dados_ref"
AORT = r"^(I35|I06|Q23[01])"
FAIXAS = ["60-69", "70-79", "80+"]
UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA", "22": "PI",
           "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
           "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
REGIAO = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}

# ---------- eventos SUS (TAVI e SAVR aórtica, inclusive AIH múltiplas com troca valvar) ----------
rd = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False,
                            usecols=["N_AIH", "IDENT", "PROC_REA", "DIAG_PRINC", "IDADE", "COD_IDADE", "DT_INTER",
                                     "CNES", "MUNIC_RES", "MUNIC_MOV", "MORTE"])
                for f in glob.glob("saida_tavi/parciais/RD*.csv*") if os.path.getsize(f) > 0]).apply(lambda s: s.str.strip())
rd = rd[rd.IDENT.eq("1")]
sp = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=["SP_NAIH", "SP_PROCREA", "SP_ATOPROF"])
                for f in glob.glob("saida_tavi/sp/parciais/SP*.csv*") if os.path.getsize(f) > 0]).apply(lambda s: s.str.strip())
mult = set(sp.loc[sp.SP_PROCREA.isin(["0415010012", "0415020034"]) & sp.SP_ATOPROF.eq("0406010692"), "SP_NAIH"])
i = pd.to_numeric(rd.IDADE, errors="coerce")
rd["idade"] = np.where(rd.COD_IDADE.eq("4"), i, np.where(rd.COD_IDADE.eq("5"), 100 + i, np.nan))
rd["ano"] = rd.DT_INTER.str[:4].astype(int)
p = rd.PROC_REA
aort = rd.DIAG_PRINC.str.match(AORT)
rd["grupo"] = np.select([p.isin(["0406011524", "0406030162"]),
                         aort & (p.eq("0406010692") | (p.isin(["0415010012", "0415020034"]) & rd.N_AIH.isin(mult)))],
                        ["TAVI", "SAVR aórtica"], "")
sus = rd[rd.grupo.ne("") & rd.ano.isin([2024, 2025])].copy()
sus = sus.rename(columns={"MUNIC_RES": "mun_res", "MUNIC_MOV": "mun_hosp"})
sus["fonte"] = "SUS"
sus["faixa"] = pd.cut(sus.idade, [-1, 59.999, 69.999, 79.999, 200], labels=["<60"] + FAIXAS).astype(str)

# ---------- eventos planos (TISS) ----------
ti = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in glob.glob("saida_tavi/tiss/parciais/*.csv*")
                if os.path.getsize(f) > 0]).drop_duplicates("ID_EVENTO_ATENCAO_SAUDE")
c = ti.cods_tuss
cids = ti[["CID_1", "CID_2", "CID_3", "CID_4"]].apply(lambda s: s.str.strip().str.upper())
ti_aort = cids.apply(lambda s: s.str.match(AORT)).any(axis=1)
ti["grupo"] = np.select([c.str.contains("30912296"),
                         c.str.contains("30902053") & ~c.str.contains("30903033|30902029") & ti_aort],
                        ["TAVI", "SAVR aórtica"], "")  # SAVR só com CID aórtico explícito (limite inferior)
ti["ano"] = pd.to_numeric(ti.ANO_MES_EVENTO.str[:4], errors="coerce")
fx = ti.FAIXA_ETARIA.str.extract(r"^(\d+)")[0].astype(float)
ti["faixa"] = np.select([fx >= 80, fx >= 70, fx >= 60], FAIXAS[::-1], "<60")
ans = ti[ti.grupo.ne("") & ti.ano.isin([2024, 2025])].rename(
    columns={"CD_MUNICIPIO_BENEFICIARIO": "mun_res", "CD_MUNICIPIO_PRESTADOR": "mun_hosp"}).copy()
ans["fonte"] = "Planos"
cols = ["fonte", "grupo", "ano", "faixa", "mun_res", "mun_hosp"]
ev = pd.concat([sus[cols + ["CNES", "idade"]], ans[cols]], ignore_index=True)
ev["mun_res"] = ev.mun_res.str[:6]
ev["mun_hosp"] = ev.mun_hosp.str[:6]
ev["uf_res"] = ev.mun_res.str[:2].map(UF_IBGE)
ev["uf_hosp"] = ev.mun_hosp.str[:2].map(UF_IBGE)
ev["regiao_res"] = ev.mun_res.str[:1].map(REGIAO)

# ---------- distâncias ----------
mun = pd.read_csv(f"{REF}/municipios_coordenadas.csv", dtype={"codigo_ibge": str})
mun["cod6"] = mun.codigo_ibge.str[:6]
coord = mun.set_index("cod6")[["latitude", "longitude"]]


def haversine(a, b):
    la1, lo1, la2, lo2 = map(np.radians, [a.latitude.values, a.longitude.values, b.latitude.values, b.longitude.values])
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(h))


ev["dist_km"] = haversine(coord.reindex(ev.mun_res), coord.reindex(ev.mun_hosp))
ev["fora_uf"] = ev.uf_res.ne(ev.uf_hosp) & ev.uf_res.notna() & ev.uf_hosp.notna()
desl = ev[ev.ano.eq(2025)].groupby(["grupo", "fonte", "regiao_res"]).agg(
    n=("dist_km", "size"), dist_mediana_km=("dist_km", "median"), dist_p75_km=("dist_km", lambda s: s.quantile(.75)),
    pct_mais_300km=("dist_km", lambda s: round(100 * (s > 300).mean(), 1)),
    pct_fora_uf=("fora_uf", lambda s: round(100 * s.mean(), 1))).round(0)
desl.to_csv(f"{S}/deslocamento_2025_por_regiao.csv")
desl_br = ev[ev.ano.eq(2025)].groupby(["grupo", "fonte"]).agg(
    n=("dist_km", "size"), dist_mediana_km=("dist_km", "median"),
    pct_mais_300km=("dist_km", lambda s: round(100 * (s > 300).mean(), 1)),
    pct_fora_uf=("fora_uf", lambda s: round(100 * s.mean(), 1)), ufs_hospital=("uf_hosp", "nunique"),
    municipios_hospital=("mun_hosp", "nunique")).round(1)
desl_br.to_csv(f"{S}/deslocamento_2025_brasil.csv")

# ---------- taxas por UF de residência (2025, ≥60, padronizadas) ----------
pop = pd.read_csv("artigo/dados_ref/populacao_uf_ano_faixa.csv")
pop = pop[(pop.ano == 2025) & pop.faixa.isin(FAIXAS)].set_index(["uf", "faixa"])["pop"]
padrao = pd.read_csv("artigo/dados_ref/populacao_uf_ano_faixa.csv")
padrao = padrao[(padrao.ano == 2022) & padrao.faixa.isin(FAIXAS)].groupby("faixa")["pop"].sum()
w = padrao / padrao.sum()
b = pd.read_csv("ciha/dados_ref/ans_beneficiarios_medicos_dezembro_uf.csv", dtype={"CD_FAIXA_E": str})
b = b[(b.ano == 2025) & b.CD_FAIXA_E.ne("99")]
cf = b.CD_FAIXA_E.astype(int)
b["faixa"] = np.select([cf >= 26, cf >= 24, cf >= 22], ["80+", "70-79", "60-69"], "<60")
ben = b[b.faixa.isin(FAIXAS)].groupby(["SG_UF", "faixa"]).NR_BENEF_M.sum()
ben.index.names = ["uf", "faixa"]
den = pd.DataFrame({"pop": pop, "benef": ben}).fillna(0)
den["sem_plano"] = den["pop"] - den["benef"]

n = ev[ev.ano.eq(2025) & ev.faixa.isin(FAIXAS)].groupby(["grupo", "fonte", "uf_res", "faixa"]).size()
linhas = []
for uf in sorted(UF_IBGE.values()):
    r = {"uf": uf}
    for g in ["TAVI", "SAVR aórtica"]:
        for fonte, dcol in [("SUS", "sem_plano"), ("Planos", "benef")]:
            taxa = pd.Series({f: 1e6 * n.get((g, fonte, uf, f), 0) / den.loc[(uf, f), dcol]
                              if den.loc[(uf, f), dcol] > 0 else np.nan for f in FAIXAS})
            r[f"{g}_{fonte}_n"] = int(sum(n.get((g, fonte, uf, f), 0) for f in FAIXAS))
            r[f"{g}_{fonte}_pm_padr"] = round(float((taxa * w).sum()), 1)
    r["cobertura_planos_60mais_pct"] = round(100 * den.loc[uf, "benef"].sum() / den.loc[uf, "pop"].sum(), 1)
    linhas.append(r)
uf_tab = pd.DataFrame(linhas).set_index("uf")
uf_tab["razao_TAVI_planos_SUS"] = (uf_tab["TAVI_Planos_pm_padr"] / uf_tab["TAVI_SUS_pm_padr"]).round(1)
uf_tab.to_csv(f"{S}/taxas_uf_residencia_2025_padronizadas.csv")

# ---------- hospitais SUS ----------
cache_p = f"{REF}/cnes_hospitais.json"
cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}
hosp = sus[sus.ano.isin([2024, 2025])].groupby(["CNES", "grupo"]).size().unstack(fill_value=0)
hosp.columns = [f"{c}_2024_2025" for c in hosp.columns]
for cnes in hosp.index:
    if cnes in cache:
        continue
    for k in range(3):
        try:
            req = urllib.request.Request(f"https://apidadosabertos.saude.gov.br/cnes/estabelecimentos/{int(cnes)}",
                                         headers={"User-Agent": "sih-crvm/1.0"})
            j = json.load(urllib.request.urlopen(req, timeout=60))
            cache[cnes] = {k2: j.get(k2) for k2 in ["nome_fantasia", "codigo_municipio", "codigo_uf",
                                                     "latitude_estabelecimento_decimo_grau",
                                                     "longitude_estabelecimento_decimo_grau",
                                                     "descricao_esfera_administrativa"]}
            break
        except Exception:
            time.sleep(2)
json.dump(cache, open(cache_p, "w"), ensure_ascii=False, indent=0)
info = pd.DataFrame.from_dict(cache, orient="index")
# localização do hospital aproximada pelo centróide do seu município (sem coordenada do estabelecimento)
_m = coord.reindex(info.codigo_municipio.astype("Int64").astype(str).str[:6])
info["latitude_estabelecimento_decimo_grau"] = _m.latitude.values
info["longitude_estabelecimento_decimo_grau"] = _m.longitude.values
hosp = hosp.join(info, how="left")
hosp["uf"] = hosp.codigo_uf.astype("Int64").astype(str).map(UF_IBGE)
t75 = sus[sus.grupo.eq("TAVI")].groupby("CNES").agg(tavi_idade_mediana=("idade", "median"),
                                                     tavi_pct_menos75=("idade", lambda s: round(100 * (s < 75).mean(), 1)))
hosp = hosp.join(t75)
hosp.sort_values(["TAVI_2024_2025", "SAVR aórtica_2024_2025"], ascending=False).to_csv(f"{S}/hospitais_sus_tavi_savr.csv")
uf_h = hosp.groupby("uf").agg(hosp_SAVR=("SAVR aórtica_2024_2025", lambda s: int((s >= 10).sum())),
                              hosp_TAVI=("TAVI_2024_2025", lambda s: int((s > 0).sum())))
uf_h = uf_h.reindex(sorted(UF_IBGE.values())).fillna(0).astype(int)
uf_h.to_csv(f"{S}/hospitais_por_uf.csv")

# ---------- mapa ----------
gj = json.load(open(f"{REF}/br_states.geojson"))


def desenhar(ax, valores, titulo, vmax):
    patches, cores = [], []
    for ft in gj["features"]:
        uf = ft["properties"]["sigla"]
        geom = ft["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            patches.append(Polygon(np.array(poly[0]), closed=True))
            cores.append(valores.get(uf, np.nan))
    pc = PatchCollection(patches, cmap="Blues", edgecolor="#555555", linewidth=0.4)
    pc.set_array(np.array(cores, dtype=float))
    pc.set_clim(0, vmax)
    ax.add_collection(pc)
    ax.set_xlim(-74.5, -34)
    ax.set_ylim(-34.5, 6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(titulo, fontsize=10)
    return pc


fig, axs = plt.subplots(1, 2, figsize=(11, 5.5))
vmax = float(np.nanpercentile(uf_tab[["TAVI_SUS_pm_padr", "TAVI_Planos_pm_padr"]].values, 95))
desenhar(axs[0], uf_tab["TAVI_SUS_pm_padr"].to_dict(), "SUS — TAVI por milhão sem plano (≥60 anos)", vmax)
pc = desenhar(axs[1], uf_tab["TAVI_Planos_pm_padr"].to_dict(), "Planos — TAVI por milhão de beneficiários (≥60)", vmax)
h = hosp[hosp["TAVI_2024_2025"] > 0]
axs[0].scatter(h.longitude_estabelecimento_decimo_grau, h.latitude_estabelecimento_decimo_grau,
               s=8 + h["TAVI_2024_2025"] / 4, c="#C00000", alpha=0.8, edgecolors="white", linewidths=0.4,
               label="hospitais SUS com TAVI")
axs[0].legend(loc="lower left", fontsize=7, frameon=False)
fig.colorbar(pc, ax=axs, shrink=0.6, label="por milhão, padronizado por idade (2025)")
fig.savefig(f"{S}/mapa_tavi_uf_2025.png", dpi=200, bbox_inches="tight")

pd.set_option("display.width", 250)
print(desl_br.to_string())
print(desl.to_string())
print(uf_tab[["TAVI_SUS_n", "TAVI_SUS_pm_padr", "TAVI_Planos_n", "TAVI_Planos_pm_padr", "razao_TAVI_planos_SUS",
              "SAVR aórtica_SUS_pm_padr", "SAVR aórtica_Planos_pm_padr", "cobertura_planos_60mais_pct"]].to_string())
print(uf_h.T.to_string())
print(hosp[hosp["TAVI_2024_2025"] > 0][["nome_fantasia", "uf", "TAVI_2024_2025", "SAVR aórtica_2024_2025",
                                        "tavi_pct_menos75"]].sort_values("TAVI_2024_2025", ascending=False).to_string())
