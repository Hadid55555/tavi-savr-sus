#!/usr/bin/env python3
"""Figuras do manuscrito TAVI (inglês), a partir dos resultados já auditados. Saída: tavi_savr/manuscrito/figuras/."""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.patches import Polygon

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
O = os.path.join(R, "manuscrito", "figuras")
os.makedirs(O, exist_ok=True)
SUS, PL, GR, INK, INK2 = "#2a78d6", "#eb6834", "#c9c8c2", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "legend.frameon": False})
nac = pd.read_csv(f"{R}/resultados_nacional/nacional_ano_faixa.csv")
pad = pd.read_csv(f"{R}/resultados_auditoria/A2_A3_taxas_padronizadas_e_limites.csv")

# ---------- Figure 1: annual volume and standardized rates ----------
a = nac[nac.ano.between(2015, 2025)].groupby("ano")[["TAVI_SUS", "TAVI_ANS", "SAVRaort_SUS", "SAVRaort_ANS_imput"]].sum()
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
for col, cor, lab in [("TAVI_SUS", SUS, "TAVI, SUS"), ("TAVI_ANS", PL, "TAVI, private plans")]:
    ax[0].plot(a.index, a[col], color=cor, lw=2, marker="o", ms=4, label=lab)
for col, cor, lab in [("SAVRaort_SUS", SUS, "SAVR (aortic), SUS"), ("SAVRaort_ANS_imput", PL, "SAVR (aortic), plans*")]:
    ax[0].plot(a.index, a[col], color=cor, lw=1.5, ls="--", label=lab)
ax[0].set_title("A  Procedures per year", loc="left", fontweight="bold")
ax[0].set_ylabel("Hospitalizations")
ax[0].legend(fontsize=7.5, loc="upper left")
ax[0].set_xticks(range(2015, 2026, 2))
p = pad[pad.ano.between(2021, 2025)]
ax[1].plot(p.ano, p.TAVI_SUS_por_sem_plano_padr60mais, color=SUS, lw=2, marker="o", ms=4, label="SUS (per million without a plan)")
ax[1].plot(p.ano, p.TAVI_ANS_por_beneficiario_padr60mais, color=PL, lw=2, marker="o", ms=4, label="Private plans (per million beneficiaries)")
for _, r in p[p.ano == 2025].iterrows():
    ax[1].annotate(f"{r.TAVI_SUS_por_sem_plano_padr60mais:.0f}", (2025, r.TAVI_SUS_por_sem_plano_padr60mais), xytext=(5, 0),
                   textcoords="offset points", va="center", color=INK)
    ax[1].annotate(f"{r.TAVI_ANS_por_beneficiario_padr60mais:.0f}", (2025, r.TAVI_ANS_por_beneficiario_padr60mais), xytext=(5, 0),
                   textcoords="offset points", va="center", color=INK)
ax[1].set_title("B  TAVI per million, age ≥60, age-standardized", loc="left", fontweight="bold")
ax[1].set_xticks(range(2021, 2026))
ax[1].set_xlim(2020.7, 2025.6)
ax[1].legend(fontsize=7.5, loc="upper left")
fig.tight_layout()
fig.savefig(f"{O}/Figure1.png", dpi=300)

# ---------- Figure 2: age ----------
F = ["60-69", "70-79", "80+"]
n25 = nac[(nac.ano == 2025) & nac.faixa.isin(F)].set_index("faixa")
pct = pd.read_csv(f"{R}/resultados_auditoria/A3_pct_TAVI_2025_limites.csv").set_index("faixa")
dist = pd.read_csv(f"{R}/resultados_nacional/distribuicao_etaria_pct.csv")
fig, ax = plt.subplots(1, 3, figsize=(12, 3.8), gridspec_kw={"width_ratios": [1, 1, 1.3]})
x = np.arange(3)
for i, (col, cor, lab) in enumerate([("TAVI_SUS_pm_dep", SUS, "SUS"), ("TAVI_ANS_pm_benef", PL, "Private plans")]):
    v = n25[col].values
    b = ax[0].bar(x + (i - 0.5) * 0.38, v, 0.36, color=cor, label=lab)
    ax[0].bar_label(b, fmt="%.0f", fontsize=7.5, padding=2, color=INK)
ax[0].set_xticks(x, ["60–69", "70–79", "≥80"])
ax[0].set_title("A  TAVI per million, 2025", loc="left", fontweight="bold")
ax[0].set_xlabel("Age (years)")
ax[0].legend(fontsize=7.5)
ax[1].bar(x - 0.19, pct.SUS.values, 0.36, color=SUS, label="SUS")
ax[1].bar(x + 0.19, pct.central.values, 0.36, color=PL, label="Private plans (central)")
ax[1].errorbar(x + 0.19, pct.central.values, yerr=[pct.central.values - pct.superior.values, pct.inferior.values - pct.central.values],
               fmt="none", ecolor=INK, capsize=3, lw=1)
for xi, v in zip(x - 0.19, pct.SUS.values):
    ax[1].text(xi, v + 2, f"{v:.0f}%", ha="center", fontsize=7.5)
for xi, v, c in zip(x + 0.19, pct.inferior.values, pct.central.values):
    ax[1].text(xi, v + 2, f"{c:.0f}%", ha="center", fontsize=7.5)
ax[1].set_xticks(x, ["60–69", "70–79", "≥80"])
ax[1].set_ylim(0, 108)
ax[1].set_title("B  TAVI as % of aortic AVR, 2025", loc="left", fontweight="bold")
ax[1].set_xlabel("Age (years)")
ax[1].legend(fontsize=7.5, loc="upper left")
d = dist[dist.grupo.eq("TAVI") & ((dist.fonte.eq("ANS") & dist.ano.between(2021, 2025)) | (dist.fonte.eq("SUS") & dist.ano.between(2024, 2025)))]
rot = [f"Plans\n{a}" if f == "ANS" else f"SUS\n{a}" for f, a in zip(d.fonte, d.ano)]
base = np.zeros(len(d))
cores = {"<60": "#e6e5e0", "60-69": "#9ec5f0", "70-79": "#2a78d6", "80+": "#163f74"}
for k, lab in [("<60", "<60"), ("60-69", "60–69"), ("70-79", "70–79"), ("80+", "≥80")]:
    ax[2].bar(range(len(d)), d[k].values, bottom=base, color=cores[k], label=lab, edgecolor="white", linewidth=1)
    base += d[k].values
ax[2].set_xticks(range(len(d)), rot, fontsize=7.5)
ax[2].set_ylabel("% of TAVI")
ax[2].set_title("C  Age distribution of TAVI", loc="left", fontweight="bold")
ax[2].legend(fontsize=7.5, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.18))
ax[2].grid(False)
fig.tight_layout()
fig.savefig(f"{O}/Figure2.png", dpi=300)

# ---------- Figure 3: maps ----------
uf = pd.read_csv(f"{R}/resultados_geografia/taxas_uf_residencia_2025_padronizadas.csv").set_index("uf")
hosp = pd.read_csv(f"{R}/resultados_geografia/hospitais_sus_tavi_savr.csv")
gj = json.load(open(f"{R}/dados_ref/br_states.geojson"))


def mapa(ax, valores, titulo, vmax):
    patches, cores = [], []
    for ft in gj["features"]:
        g = ft["geometry"]
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            patches.append(Polygon(np.array(poly[0]), closed=True))
            cores.append(valores.get(ft["properties"]["sigla"], np.nan))
    pc = PatchCollection(patches, cmap="Blues", edgecolor="white", linewidth=0.6)
    pc.set_array(np.array(cores, dtype=float))
    pc.set_clim(0, vmax)
    ax.add_collection(pc)
    ax.set_xlim(-74.5, -34)
    ax.set_ylim(-34.5, 6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(titulo, loc="left", fontweight="bold", fontsize=9)
    return pc


fig, ax = plt.subplots(1, 2, figsize=(10, 5))
vmax = 400
mapa(ax[0], uf.TAVI_SUS_pm_padr.to_dict(), "A  SUS: TAVI per million without a plan", vmax)
pc = mapa(ax[1], uf.TAVI_Planos_pm_padr.to_dict(), "B  Private plans: TAVI per million beneficiaries", vmax)
h = hosp[hosp.TAVI_2024_2025 > 0]
ax[0].scatter(h.longitude_estabelecimento_decimo_grau, h.latitude_estabelecimento_decimo_grau, s=6 + h.TAVI_2024_2025 / 3,
              facecolors="none", edgecolors=PL, linewidths=1.2, label="SUS hospitals performing TAVI (size = volume 2024–25)")
ax[0].legend(loc="lower left", fontsize=7)
cb = fig.colorbar(pc, ax=ax, shrink=0.6, extend="max")
cb.set_label("TAVI per million, age ≥60, age-standardized, 2025")
fig.savefig(f"{O}/Figure3.png", dpi=300, bbox_inches="tight")

# ---------- Figure 4: international ----------
intl = pd.read_csv(os.path.join(R, "manuscrito", "tabela_internacional.csv"))
intl = intl[intl.no_grafico.eq(1)].sort_values("tavi_por_milhao")
fig, ax = plt.subplots(figsize=(7.5, 4))
cor = [SUS if "Brazil" in s else GR for s in intl.rotulo]
b = ax.barh(intl.rotulo, intl.tavi_por_milhao, color=cor, height=0.6)
ax.bar_label(b, labels=[f"{v:.1f}" if v < 1 else f"{v:.0f}" for v in intl.tavi_por_milhao], padding=3, fontsize=8)
ax.set_xlabel("TAVI per million inhabitants (total population)")
ax.grid(axis="y", visible=False)
ax.set_xlim(0, intl.tavi_por_milhao.max() * 1.12)
fig.tight_layout()
fig.savefig(f"{O}/Figure4.png", dpi=300)
print("ok")
