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
# Paleta Lancet (ggsci "lancet"): SUS navy, planos vermelho, neutros cinza-azulado; Liberation Sans (métrica Arial)
SUS, PL, GR, INK, INK2 = "#00468B", "#ED0000", "#ADB6B6", "#1B1B1B", "#5B6770"
NAVY_D = "#002B55"
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#E5E8EA", "grid.linewidth": 0.6, "axes.axisbelow": True,
                     "legend.frameon": False})
nac = pd.read_csv(f"{R}/resultados_nacional/nacional_ano_faixa.csv")
pad = pd.read_csv(f"{R}/resultados_auditoria/A2_A3_taxas_padronizadas_e_limites.csv")

# ---------- Figure 1: annual volume and standardized rates ----------
a = nac[nac.ano.between(2015, 2025)].groupby("ano")[["TAVI_SUS", "TAVI_ANS", "SAVRaort_SUS", "SAVRaort_ANS_imput"]].sum()
fig, ax = plt.subplots(1, 2, figsize=(10, 4.2))
for col, cor, mk, lab in [("TAVI_SUS", SUS, "o", "TAVI, SUS"), ("TAVI_ANS", PL, "s", "TAVI, private plans")]:
    ax[0].plot(a.index, a[col], color=cor, lw=2, marker=mk, ms=5, label=lab)
for col, cor, mk, lab in [("SAVRaort_SUS", SUS, "o", "SAVR (aortic), SUS"), ("SAVRaort_ANS_imput", PL, "s", "SAVR (aortic), plans*")]:
    ax[0].plot(a.index, a[col], color=cor, lw=1.5, ls="--", marker=mk, ms=4.5, mfc="white", label=lab)
ymax = a.values.max() * 1.18
for xe, txt in [(2021, "Plan coverage\n(DUT 143, Apr 2021)"), (2024, "SUS TAVI code\n(2023–24)")]:
    ax[0].axvline(xe, color=INK2, lw=0.8, ls=":")
    ax[0].text(xe - 0.12, ymax * 0.97, txt, ha="right", va="top", fontsize=7.5, color=INK2)
ax[0].set_ylim(0, ymax)
ax[0].set_title("A  Procedures per year", loc="left", fontweight="bold")
ax[0].set_ylabel("Hospitalizations")
ax[0].legend(fontsize=8, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.12))
ax[0].set_xticks(range(2015, 2026, 2))
p = pad[pad.ano.between(2021, 2025)]
ax[1].plot(p.ano, p.TAVI_SUS_por_sem_plano_padr60mais, color=SUS, lw=2, marker="o", ms=5, label="SUS (per million without plan coverage)")
ax[1].plot(p.ano, p.TAVI_ANS_por_beneficiario_padr60mais, color=PL, lw=2, marker="s", ms=5, label="Private plans (per million beneficiaries)")
for _, r in p[p.ano == 2025].iterrows():
    for v in [r.TAVI_SUS_por_sem_plano_padr60mais, r.TAVI_ANS_por_beneficiario_padr60mais]:
        ax[1].annotate(f"{v:.0f}", (2025, v), xytext=(6, 0), textcoords="offset points", va="center", color=INK, fontweight="bold")
ax[1].set_title("B  TAVI per million, age ≥60, age-standardized", loc="left", fontweight="bold")
ax[1].set_xticks(range(2021, 2026))
ax[1].set_xlim(2020.7, 2025.7)
ax[1].legend(fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(f"{O}/Figure1.png", dpi=300)

# ---------- Figure 2: age (A rates, B % TAVI); Supplementary Figure S2: age distribution ----------
F = ["60-69", "70-79", "80+"]
n25 = nac[(nac.ano == 2025) & nac.faixa.isin(F)].set_index("faixa")
pct = pd.read_csv(f"{R}/resultados_auditoria/A3_pct_TAVI_2025_limites.csv").set_index("faixa")
dist = pd.read_csv(f"{R}/resultados_nacional/distribuicao_etaria_pct.csv")
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
x = np.arange(3)
for i, (col, cor, hat, lab) in enumerate([("TAVI_SUS_pm_dep", SUS, None, "SUS"), ("TAVI_ANS_pm_benef", PL, "///", "Private plans")]):
    v = n25[col].values
    b = ax[0].bar(x + (i - 0.5) * 0.38, v, 0.36, color=cor, hatch=hat, edgecolor="white", label=lab)
    ax[0].bar_label(b, fmt="%.0f", fontsize=8, padding=2, color=INK)
ax[0].set_xticks(x, ["60–69", "70–79", "≥80"])
ax[0].set_title("A  TAVI per million, 2025", loc="left", fontweight="bold")
ax[0].set_xlabel("Age (years)")
ax[0].legend(fontsize=8)
ax[1].bar(x - 0.19, pct.SUS.values, 0.36, color=SUS, edgecolor="white", label="SUS")
ax[1].bar(x + 0.19, pct.central.values, 0.36, color=PL, hatch="///", edgecolor="white", label="Private plans (central; whiskers = bounds)")
ax[1].errorbar(x + 0.19, pct.central.values, yerr=[pct.central.values - pct.superior.values, pct.inferior.values - pct.central.values],
               fmt="none", ecolor=INK, capsize=3, lw=1)
for xi, v in zip(x - 0.19, pct.SUS.values):
    ax[1].text(xi, v + 2, f"{v:.0f}%", ha="center", fontsize=8)
for xi, v, c in zip(x + 0.19, pct.inferior.values, pct.central.values):
    ax[1].text(xi, v + 2, f"{c:.0f}%", ha="center", fontsize=8)
ax[1].set_xticks(x, ["60–69", "70–79", "≥80"])
ax[1].set_ylim(0, 110)
ax[1].set_title("B  TAVI as % of aortic AVR, 2025", loc="left", fontweight="bold")
ax[1].set_xlabel("Age (years)")
ax[1].legend(fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(f"{O}/Figure2.png", dpi=300)

fig, ax2 = plt.subplots(figsize=(7, 4))
d = dist[dist.grupo.eq("TAVI") & ((dist.fonte.eq("ANS") & dist.ano.between(2021, 2025)) | (dist.fonte.eq("SUS") & dist.ano.between(2024, 2025)))]
rot = [f"Plans\n{a}" if f == "ANS" else f"SUS\n{a}" for f, a in zip(d.fonte, d.ano)]
base = np.zeros(len(d))
cores = {"<60": "#DDE3E8", "60-69": "#8FB3D9", "70-79": "#3A73B0", "80+": "#00468B"}
for k, lab in [("<60", "<60"), ("60-69", "60–69"), ("70-79", "70–79"), ("80+", "≥80")]:
    bb = ax2.bar(range(len(d)), d[k].values, bottom=base, color=cores[k], label=lab, edgecolor="white", linewidth=1)
    if k in ("70-79", "80+"):
        ax2.bar_label(bb, labels=[f"{v:.0f}" for v in d[k].values], label_type="center", fontsize=7.5, color="white")
    base += d[k].values
ax2.set_xticks(range(len(d)), rot, fontsize=8)
ax2.set_ylabel("% of TAVI")
ax2.set_title("Age distribution of TAVI by payer and year", loc="left", fontweight="bold")
ax2.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.16), title="Age (years)", title_fontsize=8)
ax2.grid(False)
fig.tight_layout()
fig.savefig(f"{O}/FigureS2.png", dpi=300)

# ---------- Figure 3: maps ----------
uf = pd.read_csv(f"{R}/resultados_geografia/taxas_uf_residencia_2025_padronizadas.csv").set_index("uf")
hosp = pd.read_csv(f"{R}/resultados_geografia/hospitais_sus_tavi_savr.csv")
gj = json.load(open(f"{R}/dados_ref/br_states.geojson"))


from matplotlib.colors import BoundaryNorm, ListedColormap
BOUNDS = [0.001, 5, 25, 100, 200, 400, 2000]
CMAP = ListedColormap(["#E3ECF5", "#B7CDE6", "#7FA6D0", "#4479B3", "#00468B", "#002B55"])
NORM = BoundaryNorm(BOUNDS, CMAP.N)


def mapa(ax, valores, titulo):
    patches, cores, zeros = [], [], []
    for ft in gj["features"]:
        g = ft["geometry"]
        v = valores.get(ft["properties"]["sigla"], np.nan)
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            p = np.array(poly[0])
            (zeros if v == 0 else patches).append(Polygon(p, closed=True))
            if v != 0:
                cores.append(v)
    pc = PatchCollection(patches, cmap=CMAP, norm=NORM, edgecolor="white", linewidth=0.6)
    pc.set_array(np.array(cores, dtype=float))
    ax.add_collection(pc)
    if zeros:
        ax.add_collection(PatchCollection(zeros, facecolor="#EEF0F1", edgecolor="white", linewidth=0.6, hatch="////"))
    ax.set_xlim(-74.5, -34)
    ax.set_ylim(-34.5, 6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(titulo, loc="left", fontweight="bold", fontsize=9)
    return pc


fig, ax = plt.subplots(1, 2, figsize=(10, 5.3))
mapa(ax[0], uf.TAVI_SUS_pm_padr.to_dict(), "A  SUS: TAVI per million without plan coverage")
pc = mapa(ax[1], uf.TAVI_Planos_pm_padr.to_dict(), "B  Private plans: TAVI per million beneficiaries")
h = hosp[hosp.TAVI_2024_2025 > 0]
ax[0].scatter(h.longitude_estabelecimento_decimo_grau, h.latitude_estabelecimento_decimo_grau, s=6 + h.TAVI_2024_2025 / 3,
              facecolors="none", edgecolors=INK, linewidths=1.1, label="SUS TAVI centres (size = volume 2024–25)")
from matplotlib.patches import Patch
ax[0].legend(handles=[ax[0].collections[-1], Patch(facecolor="#EEF0F1", hatch="////", edgecolor="#8A949A", label="No TAVI recorded")],
             loc="upper left", bbox_to_anchor=(0.0, 0.02), fontsize=7.5, frameon=False, ncol=2)
cb = fig.colorbar(pc, ax=ax, shrink=0.6, ticks=BOUNDS[:-1], spacing="uniform")
cb.ax.set_yticklabels([">0", "5", "25", "100", "200", "400"])
cb.set_label("TAVI per million, age ≥60, age-standardized, 2025")
fig.savefig(f"{O}/Figure3.png", dpi=300, bbox_inches="tight")

# ---------- Figure 4: international context ----------
intl = pd.read_csv(os.path.join(R, "manuscrito", "tabela_internacional.csv"))
ref = intl[intl.grupo.str.startswith("Reference")].set_index("rotulo").tavi_por_milhao
bars = intl[intl.no_grafico.eq(1) & ~intl.grupo.str.startswith("Reference")]
ordem = ["High-income countries", "High-income countries, earlier adoption", "Brazil (this study)"]
rows, ys, y = [], [], 0
gy = {}
for g in ordem:
    sub = bars[bars.grupo.eq(g)].sort_values("tavi_por_milhao", ascending=False)
    gy[g] = y
    y += 0.9
    for _, r in sub.iterrows():
        rows.append(r)
        ys.append(y)
        y += 1
    y += 0.4
rows = pd.DataFrame(rows)
fig, ax = plt.subplots(figsize=(7.5, 5.2))
cor = [SUS if "SUS +" in s else "#7FA6D0" if "SUS only" in s else GR for s in rows.rotulo]
b = ax.barh(ys, rows.tavi_por_milhao, color=cor, height=0.7)
ax.bar_label(b, labels=[f"{v:.1f}" if v < 20 else f"{v:.0f}" for v in rows.tavi_por_milhao], padding=3, fontsize=8.5)
ax.set_yticks(ys, rows.rotulo, fontsize=8.5)
for g, yy in gy.items():
    ax.text(-0.01, yy, g.replace(", earlier adoption", ": earlier adoption"), transform=ax.get_yaxis_transform(), ha="right",
            va="center", fontsize=8.5, fontweight="bold", color=INK)
ax.invert_yaxis()
hi = ref.filter(like="high-income").iloc[0]
mi = ref.filter(like="middle-income").iloc[0]
for v, txt in [(hi, f"ESC high-income median {hi:.0f}"), (mi, f"ESC middle-income median {mi:.0f}")]:
    ax.axvline(v, color=INK2, lw=1, ls="--")
    ax.text(v + 2, ys[-1] + 0.9 if v < 50 else -0.2, txt, fontsize=7.5, color=INK2, va="center")
ax.set_xlabel("TAVI per million inhabitants (total population)")
ax.set_title("International context: TAVI per million inhabitants", loc="left", fontweight="bold")
ax.grid(axis="y", visible=False)
ax.grid(axis="x", visible=True)
ax.set_xlim(0, rows.tavi_por_milhao.max() * 1.15)
ax.set_ylim(ys[-1] + 1.5, -0.9)
fig.tight_layout()
fig.savefig(f"{O}/Figure4.png", dpi=300, bbox_inches="tight")
print("ok")
