#!/usr/bin/env python3
"""Build the pseudonymized analytic data of this package from the raw extracts of the original project.

Run from the ORIGINAL project root (the one with saida_tavi/ raw extracts), with the package root as argument:
    python tools/build_package_data.py /path/to/package [/path/to/private_mapping.json]

What it does
- Concatenates the per-file extracts (SIH/SUS RD, SIH/SUS SP, ANS TISS, TISS plan counts) into single gzip files placed at
  the paths the analysis scripts read (glob patterns RD*.csv*, SP*.csv*, tiss/parciais/*.csv*).
- Replaces hospital identifiers (CNES) and hospitalization identifiers (AIH number) with meaningless codes, using one
  random mapping for all files (CNES -> H######, AIH -> A############). The mapping is NOT saved in the package; it is
  written only to the optional second argument, outside the package, for the reproducibility check, and then deleted.
- SIH/SUS SP: keeps only the rows of multiple-surgery hospitalizations (procedure 04.15.01.001-2 / 04.15.02.003-4), which
  are the only SP rows the analyses use, and only 6 columns (no professional identifiers: CNS, CPF/CNPJ, CBO removed).
- Hospital reference table: CNES-API fields reduced to municipality, state and administrative sphere; the establishment
  name is replaced by the pseudonymous code and coordinates are not kept (analyses use the municipality centroid).
- CNES accreditation file: only the cardiovascular accreditation groups 08.01, 08.02, 08.03, 08.15, and only the columns
  used (no CNPJ, postal code or other establishment identifiers).
"""
import glob
import json
import os
import random
import sys

import pandas as pd
import pyarrow.parquet as pq

PKG = sys.argv[1]
MAPOUT = sys.argv[2] if len(sys.argv) > 2 else None
rng = random.Random()  # system entropy; mapping differs at every build


def out(p):
    path = os.path.join(PKG, p)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def ler(pattern, **kw):
    fs = sorted(f for f in glob.glob(pattern) if os.path.getsize(f) > 0)
    return pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, **kw) for f in fs], ignore_index=True)


rd = ler("saida_tavi/parciais/RD*.csv")
sp = ler("saida_tavi/sp/parciais/SP*.csv", usecols=["SP_NAIH", "SP_CNES", "SP_PROCREA", "SP_ATOPROF", "SP_DTINTER",
                                                     "SP_CIDPRI"])
sp = sp[sp.SP_PROCREA.str.strip().isin(["0415010012", "0415020034"])]
hab = pq.read_table("saida_tavi/kaggle_raw/cnes_habilitacoes.parquet").to_pandas().astype(str)
hab = hab[hab.SGRUPHAB.isin(["0801", "0802", "0803", "0815"])][
    ["CNES", "CODUFMUN", "SGRUPHAB", "CMPT_INI", "CMPT_FIM", "PORTARIA", "DTPORTAR", "COMPETEN"]]  # no CNPJ, CEP, address
cache = json.load(open("tavi_savr/dados_ref/cnes_hospitais.json"))
src_v2 = open("tavi_savr/analises_v2.py", encoding="utf-8").read()
habil = src_v2[src_v2.index("HABILITADOS = ["):src_v2.index("]", src_v2.index("HABILITADOS = ["))]
import re
habil = re.findall(r'"(\d{7})"', habil)

# ---------- mappings ----------
cnes_all = sorted(set(rd.CNES.str.strip()) | set(sp.SP_CNES.str.strip()) | set(hab.CNES.str.strip()) | set(cache) |
                  set(habil))
cnes_all = [c for c in cnes_all if c]
cod = rng.sample(range(100000, 1000000), len(cnes_all))
mcnes = {c: f"H{n}" for c, n in zip(cnes_all, cod)}
aih_all = sorted(set(rd.N_AIH.str.strip()) | set(sp.SP_NAIH.str.strip()))
cod = rng.sample(range(10 ** 11, 10 ** 12), len(aih_all))
maih = {a: f"A{n}" for a, n in zip(aih_all, cod)}


def pc(s):
    st = s.str.strip()
    return st.map(mcnes).fillna(st)


def pa(s):
    st = s.str.strip()
    return st.map(maih).fillna(st)


# ---------- SIH/SUS RD and SP ----------
rd["CNES"] = pc(rd.CNES)
rd["N_AIH"] = pa(rd.N_AIH)
rd.to_csv(out("saida_tavi/parciais/RD_valvas_2008_2026.csv.gz"), index=False)
sp["SP_CNES"] = pc(sp.SP_CNES)
sp["SP_NAIH"] = pa(sp.SP_NAIH)
sp.to_csv(out("saida_tavi/sp/parciais/SP_multiplas_2008_2026.csv.gz"), index=False)

# ---------- TISS (no hospital or patient identifier in the open data) ----------
ler("saida_tavi/tiss/parciais/*.csv").to_csv(out("saida_tavi/tiss/parciais/tiss_valvas_2015_2025.csv.gz"), index=False)
with open("saida_tavi/tiss/parciais/_cobertura.jsonl") as f, open(out("saida_tavi/tiss/parciais/_cobertura.jsonl"), "w") as g:
    g.write(f.read())
pl = pd.concat([pd.read_csv(f, dtype={"ID_PLANO": str}) for f in glob.glob("saida_tavi/tiss_planos/parciais/*.csv")
                if os.path.getsize(f) > 0], ignore_index=True)
pl.groupby(["ID_PLANO", "uf", "ano"], as_index=False)["internacoes"].sum().to_csv(
    out("saida_tavi/tiss_planos/parciais/tiss_internacoes_plano_uf_ano.csv.gz"), index=False)

# ---------- SIM (deaths with I35/I06 in any field; no personal identifier) ----------
pd.read_csv("saida_tavi/sim_valva_aortica_obitos.csv", dtype=str, keep_default_na=False).to_csv(
    out("saida_tavi/sim_valva_aortica_obitos.csv.gz"), index=False)

# ---------- CNES ----------
hab["CNES"] = pc(hab.CNES)
os.makedirs(os.path.dirname(out("saida_tavi/kaggle_raw/x")), exist_ok=True)
hab.to_parquet(out("saida_tavi/kaggle_raw/cnes_habilitacoes.parquet"), index=False)
c2 = {mcnes[k]: {"nome_fantasia": mcnes[k], "codigo_municipio": v.get("codigo_municipio"), "codigo_uf": v.get("codigo_uf"),
                 "latitude_estabelecimento_decimo_grau": None, "longitude_estabelecimento_decimo_grau": None,
                 "descricao_esfera_administrativa": v.get("descricao_esfera_administrativa")} for k, v in cache.items()}
json.dump(c2, open(out("tavi_savr/dados_ref/cnes_hospitais.json"), "w"), ensure_ascii=False, indent=0)

# accredited-hospital list in analises_v2.py -> pseudonymous codes
s = open(out("tavi_savr/analises_v2.py"), encoding="utf-8").read()
for c in habil:
    s = s.replace(f'"{c}"', f'"{mcnes[c]}"')
open(out("tavi_savr/analises_v2.py"), "w", encoding="utf-8").write(s)

if MAPOUT:
    json.dump({"cnes": mcnes, "aih": maih}, open(MAPOUT, "w"))
print("CNES mapped:", len(mcnes), "| AIH mapped:", len(maih), "| RD rows:", len(rd), "| SP rows:", len(sp))
