#!/usr/bin/env python3
"""Tabela 1 do manuscrito: características das internações de TAVI e SAVR aórtica, SUS × planos, 2024–2025 (ano da
internação/evento). Mesmas definições de nacional_sus_ans.py. Planos: SAVR aórtica = TUSS 30902053 com CID aórtico
explícito (limite inferior). Saída: tavi_savr/manuscrito/tabela1.csv."""
import glob
import os

import numpy as np
import pandas as pd

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
AORT = r"^(I35|I06|Q23[01])"
rd = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in glob.glob("saida_tavi/parciais/RD*.csv*")
                if os.path.getsize(f) > 0], ignore_index=True).apply(lambda s: s.str.strip())
rd = rd[rd.IDENT.eq("1")]
i = pd.to_numeric(rd.IDADE, errors="coerce")
rd["idade"] = np.where(rd.COD_IDADE.eq("4"), i, np.where(rd.COD_IDADE.eq("5"), 100 + i, np.nan))
rd["ano"] = rd.DT_INTER.str[:4].astype(int)
sp = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, usecols=["SP_NAIH", "SP_PROCREA", "SP_ATOPROF"])
                for f in glob.glob("saida_tavi/sp/parciais/SP*.csv*") if os.path.getsize(f) > 0]).apply(lambda s: s.str.strip())
mult = set(sp.loc[sp.SP_PROCREA.isin(["0415010012", "0415020034"]) & sp.SP_ATOPROF.eq("0406010692"), "SP_NAIH"])
p = rd.PROC_REA
aort = rd.DIAG_PRINC.str.match(AORT)
rd["g"] = np.select([p.isin(["0406011524", "0406030162"]),
                     aort & (p.eq("0406010692") | (p.isin(["0415010012", "0415020034"]) & rd.N_AIH.isin(mult)))],
                    ["TAVI", "SAVR"], "")
sus = rd[rd.g.ne("") & rd.ano.isin([2024, 2025])].copy()
ti = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in glob.glob("saida_tavi/tiss/parciais/*.csv*")
                if os.path.getsize(f) > 0]).drop_duplicates("ID_EVENTO_ATENCAO_SAUDE")
c = ti.cods_tuss
cids = ti[["CID_1", "CID_2", "CID_3", "CID_4"]].apply(lambda s: s.str.strip().str.upper())
ti_aort = cids.apply(lambda s: s.str.match(AORT)).any(axis=1)
ti["g"] = np.select([c.str.contains("30912296"), c.str.contains("30902053") & ~c.str.contains("30903033|30902029") & ti_aort],
                    ["TAVI", "SAVR"], "")
ti = ti[ti.g.ne("") & ti.ANO_MES_EVENTO.str[:4].isin(["2024", "2025"])].copy()
fx = ti.FAIXA_ETARIA.str.extract(r"^(\d+)")[0].astype(float)


def pct(m):
    return f"{int(m.sum()):,} ({100 * m.mean():.1f})"


def faixas_sus(x):
    return {"<60": x < 60, "60–69": x.between(60, 69), "70–79": x.between(70, 79), "  70–74 (SUS only)": x.between(70, 74),
            "  75–79 (SUS only)": x.between(75, 79), "≥80": x >= 80}


cols = {}
for g in ["TAVI", "SAVR"]:
    s = sus[sus.g.eq(g)]
    r = {"Hospitalizations, n": f"{len(s):,}",
         "Age, median (IQR), years": f"{s.idade.median():.0f} ({s.idade.quantile(.25):.0f}–{s.idade.quantile(.75):.0f})"}
    for k, m in faixas_sus(s.idade).items():
        r[f"Age {k.strip()}, n (%)"] = pct(m)
    r["Female, n (%)"] = pct(s.SEXO.isin(["3", "2"]))
    r["Urgent admission, n (%)"] = pct(s.CAR_INT.ne("01"))
    r["Principal diagnosis I35.0 (aortic stenosis), n (%)"] = pct(s.DIAG_PRINC.str.startswith("I350"))
    r["Principal diagnosis I06 (rheumatic), n (%)"] = pct(s.DIAG_PRINC.str.startswith("I06"))
    r["Length of stay, median (IQR), days"] = (f"{pd.to_numeric(s.DIAS_PERM).median():.0f} "
                                               f"({pd.to_numeric(s.DIAS_PERM).quantile(.25):.0f}–{pd.to_numeric(s.DIAS_PERM).quantile(.75):.0f})")
    r["In-hospital death, n (%)"] = pct(pd.to_numeric(s.MORTE, errors="coerce").fillna(0).eq(1))
    r["Hospitals, n"] = f"{s.CNES.nunique()}"
    r["States of hospital, n"] = f"{s.MUNIC_MOV.str[:2].nunique()}"
    cols[f"{g} — SUS"] = r
    t = ti[ti.g.eq(g)]
    f = fx[t.index] if False else t.FAIXA_ETARIA.str.extract(r"^(\d+)")[0].astype(float)
    r = {"Hospitalizations, n": f"{len(t):,}", "Age, median (IQR), years": "n/a (10-year bands)"}
    for k, m in {"<60": f < 60, "60–69": f.eq(60), "70–79": f.eq(70), "  70–74 (SUS only)": None, "  75–79 (SUS only)": None,
                 "≥80": f >= 80}.items():
        r[f"Age {k.strip()}, n (%)"] = pct(m) if m is not None else "—"
    r["Female, n (%)"] = pct(t.SEXO.str.upper().str.startswith("F"))
    r["Urgent admission, n (%)"] = pct(t.CD_CARATER_ATENDIMENTO.str.strip().eq("2"))
    r["Principal diagnosis I35.0 (aortic stenosis), n (%)"] = pct(t.CID_1.str.strip().str.upper().str.startswith("I350"))
    r["Principal diagnosis I06 (rheumatic), n (%)"] = pct(t.CID_1.str.strip().str.upper().str.startswith("I06"))
    lp = pd.to_numeric(t.TEMPO_DE_PERMANENCIA, errors="coerce")
    r["Length of stay, median (IQR), days"] = f"{lp.median():.0f} ({lp.quantile(.25):.0f}–{lp.quantile(.75):.0f})"
    r["In-hospital death, n (%)"] = pct(t.CD_MOTIVO_SAIDA.str.strip().isin(["41", "42", "43"]))
    r["Hospitals, n"] = "n/a"
    r["States of hospital, n"] = f"{t.UF_PRESTADOR.str.strip().replace('', np.nan).dropna().nunique()}"
    cols[f"{g} — private plans"] = r
tab = pd.DataFrame(cols)[["TAVI — SUS", "TAVI — private plans", "SAVR — SUS", "SAVR — private plans"]]
tab.to_csv("tavi_savr/manuscrito/tabela1.csv")
print(tab.to_string())
print(ti.SEXO.value_counts().head(), ti.CD_CARATER_ATENDIMENTO.value_counts().head(), sus.SEXO.value_counts(), sus.CAR_INT.value_counts().head())
