#!/usr/bin/env python3
"""TAVI e SAVR isolada aórtica em pacientes ≥75 anos por milhão de habitantes ≥75 (Brasil, IBGE projeção rev. 2018,
SIDRA 7358, já em artigo/dados_ref/proj7358.json). Lê tavi_savr/resultados_fase1/faixa_etaria_ano.csv."""
import json

import pandas as pd

p = pd.DataFrame(json.load(open("artigo/dados_ref/proj7358.json"))[1:])
p["V"] = pd.to_numeric(p["V"], errors="coerce")
p["ano"] = p["D6N"].astype(int)
piv = p.pivot_table(index="ano", columns="D5N", values="V", aggfunc="sum")
# "80 anos ou mais" existe em todos os anos (2008–2009 não têm 80-84/85-89/90+)
pop75 = piv["75 a 79 anos"] + piv["80 anos ou mais"]

fx = pd.read_csv("tavi_savr/resultados_fase1/faixa_etaria_ano.csv")
fx["ge75"] = fx[["75-79", "80-84", "85+"]].sum(axis=1)
t = fx[fx["ano"].between(2008, 2025)].pivot(index="ano", columns="grupo", values="ge75").fillna(0)
t["pop75_milhoes"] = (pop75.reindex(t.index) / 1e6).round(3)
t["SAVR_por_milhao75"] = (t["SAVR isolada (aórtica)"] / t["pop75_milhoes"]).round(1)
t["TAVI_por_milhao75"] = (t["TAVI"] / t["pop75_milhoes"]).round(1)
t["pct_TAVI_entre_AVR_75mais"] = (100 * t["TAVI"] / (t["TAVI"] + t["SAVR isolada (aórtica)"])).round(1)
t.to_csv("tavi_savr/resultados_fase1/taxa_por_milhao_75mais.csv")
print(t.to_string())
