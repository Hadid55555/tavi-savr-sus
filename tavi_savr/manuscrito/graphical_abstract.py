#!/usr/bin/env python3
"""Graphical abstract (16:9, mesmo molde do OPCAB): três painéis com número-chave + mini-gráfico e mensagem final.
Lê só resultados já gerados. Saída: tavi_savr/manuscrito/figuras/GraphicalAbstract.png/.pdf/.tiff"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
O = os.path.join(R, "manuscrito", "figuras")
plt.rcParams["font.family"] = "Liberation Sans"
INK, MUT, OR, NAV, GR, LN = "#1B1B1B", "#5B6770", "#ED0000", "#00468B", "#ADB6B6", "#D5DADD"

pad = pd.read_csv(f"{R}/resultados_auditoria/A2_A3_taxas_padronizadas_e_limites.csv")
pad = pad[pad.ano.between(2021, 2025)]
r6 = pd.read_csv(f"{R}/resultados_v2/R6_distancia_centro_tavi_mais_proximo.csv")
intl = pd.read_csv(os.path.join(R, "manuscrito", "tabela_internacional.csv")).set_index("rotulo")
nac = pd.read_csv(f"{R}/resultados_nacional/nacional_ano_faixa.csv")
n_tavi = 1123 + 6222  # SUS + plans, 2021–2025 (manuscript, Results)

fig = plt.figure(figsize=(12.8, 7.2), dpi=300)
fig.text(0.04, 0.915, "TAVI in Brazil’s Public and Private Health Sectors, 2015–2025", fontsize=25, weight="bold", color=INK)
fig.text(0.04, 0.866, f"Nationwide SIH/SUS and ANS TISS data · {n_tavi:,} TAVI hospitalizations (2021–2025) · 27 states",
         fontsize=13, color=MUT)
fig.add_artist(plt.Line2D([0.04, 0.96], [0.835, 0.835], color=INK, lw=2.2))
for x in (0.34, 0.66):
    fig.add_artist(plt.Line2D([x, x], [0.21, 0.80], color=LN, lw=1))


def cab(x, letra, titulo, num, cor, sub):
    fig.text(x, 0.765, f"{letra} · {titulo}", fontsize=16, weight="bold", color=INK)
    fig.text(x, 0.655, num, fontsize=40, weight="bold", color=cor)
    fig.text(x, 0.615, sub, fontsize=11.5, color=INK)


def limpa(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(MUT)
    ax.spines["bottom"].set_color(MUT)
    ax.tick_params(colors=MUT, labelsize=10.5)


# ---------- A: payer ----------
cab(0.04, "A", "Payer gap", "6.8×", OR, "higher TAVI rate in private plans than in the SUS")
ax = fig.add_axes([0.075, 0.335, 0.2, 0.22])
ax.plot(pad.ano, pad.TAVI_ANS_por_beneficiario_padr60mais, color=OR, lw=2.4)
ax.plot(pad.ano, pad.TAVI_SUS_por_sem_plano_padr60mais, color=NAV, lw=2.4)
u = pad.iloc[-1]
ax.text(2025.15, u.TAVI_ANS_por_beneficiario_padr60mais, f"Plans {u.TAVI_ANS_por_beneficiario_padr60mais:.0f}",
        color=OR, fontsize=11, weight="bold", va="center")
ax.text(2025.15, u.TAVI_SUS_por_sem_plano_padr60mais + 6, f"SUS {u.TAVI_SUS_por_sem_plano_padr60mais:.0f}", color=NAV,
        fontsize=11, weight="bold", va="center")
ax.set_xticks([2021, 2023, 2025]); ax.set_ylim(0, 230); ax.set_yticks([0, 100, 200]); ax.set_xlim(2020.8, 2025)
limpa(ax)
fig.text(0.04, 0.215, "Per million, ≥60 y, age-standardized · same rule:\n≥75 y and inoperable/high risk in both sectors",
         fontsize=10.5, color=MUT, style="italic")

# ---------- B: geography ----------
cab(0.36, "B", "Geography", "10 of 27", NAV, "states with no SUS TAVI in 2025")
ax = fig.add_axes([0.47, 0.335, 0.15, 0.22])
g = r6.set_index(["grupo", "regiao"]).mediana_km
lab = ["TAVI recipients", "SAVR ≥70 · Brazil", "SAVR ≥70 · Northeast", "SAVR ≥70 · North"]
val = [g[("TAVI (SUS)", "Brasil")], g[("SAVR aórtica ≥70 (SUS)", "Brasil")], g[("SAVR aórtica ≥70 (SUS)", "Nordeste")],
       g[("SAVR aórtica ≥70 (SUS)", "Norte")]]
cores = [NAV, GR, GR, "#002B55"]
b = ax.barh(range(4)[::-1], val, color=cores, height=0.6)
for i, v in zip(range(4)[::-1], val):
    ax.text(v + 12, i, f"{v:.0f} km", va="center", fontsize=10.5, color=INK)
ax.set_yticks(range(4)[::-1], lab, fontsize=10.5, color=INK)
ax.set_xlim(0, 640); ax.set_xticks([0, 250, 500])
limpa(ax)
fig.text(0.36, 0.215, "Median distance to the nearest active SUS TAVI centre\n(SUS patients)", fontsize=10.5, color=MUT,
         style="italic")

# ---------- C: volume ----------
cab(0.68, "C", "Volume", "12 / million", NAV, "TAVI per million inhabitants in Brazil, 2025")
ax = fig.add_axes([0.80, 0.335, 0.13, 0.22])
paises = [("France (2019)", "France"), ("Spain (2023)", "Spain"), ("England (2022/23)", "England"), ("Poland (2019)", "Poland"),
          ("Brazil, SUS + private plans (2025)", "Brazil"), ("ESC middle-income countries, median (2023)", "ESC middle-income")]
v = [intl.loc[k, "tavi_por_milhao"] for k, _ in paises]
ax.barh(range(len(v))[::-1], v, color=[NAV if n == "Brazil" else GR for _, n in paises], height=0.6)
for i, x in zip(range(len(v))[::-1], v):
    ax.text(x + 4, i, f"{x:.0f}", va="center", fontsize=10.5, color=INK)
ax.set_yticks(range(len(v))[::-1], [n for _, n in paises], fontsize=10.5, color=INK)
ax.set_xlim(0, 230); ax.set_xticks([0, 100, 200])
limpa(ax)
fig.text(0.68, 0.215, "No shift to younger patients: ≥80 y = 58% → 60%\nof plan TAVI (2021 → 2025)", fontsize=10.5,
         color=MUT, style="italic")

# ---------- message ----------
fig.add_artist(FancyBboxPatch((0.04, 0.03), 0.92, 0.135, boxstyle="square,pad=0", fc="#EEF2F6", ec="none"))
t1 = fig.text(0.06, 0.112, "TAVI grew fast, but far below high-income volumes — ", fontsize=15.5, weight="bold", color=INK)
fig.canvas.draw()
bb = t1.get_window_extent().transformed(fig.transFigure.inverted())
fig.text(bb.x1, 0.112, "a sevenfold payer gap under the same age rule", fontsize=15.5, weight="bold", color=OR)
fig.text(0.06, 0.058, "Public access depends on living near an active centre; judicial requests continued after "
         "incorporation, increasingly for patients <75 years.", fontsize=12.5, color=INK)
os.makedirs(O, exist_ok=True)
for ext in ("png", "pdf", "tiff"):
    fig.savefig(f"{O}/GraphicalAbstract.{ext}", dpi=300, facecolor="white")
print("ok")
