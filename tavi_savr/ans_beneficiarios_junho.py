#!/usr/bin/env python3
"""Beneficiários de planos médico-hospitalares em junho (meio do ano), por UF e faixa etária, 2021–2025 (ANS, dados
abertos "informações consolidadas de beneficiários", pda-024). Sensibilidade ao denominador de dezembro usado na análise
principal (ciha/dados_ref/ans_beneficiarios_medicos_dezembro_uf.csv). Saída: tavi_savr/dados_ref/ans_beneficiarios_junho_uf_faixa.csv
Uso: python -I tavi_savr/ans_beneficiarios_junho.py
"""
import io
import os
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

B = "https://dadosabertos.ans.gov.br/FTP/PDA/informacoes_consolidadas_de_beneficiarios-024"
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split()


def um(uf, ano):
    url = f"{B}/{ano}06/pda-024-icb-{uf}-{ano}_06.zip"
    for i in range(4):
        try:
            dados = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "sih-crvm/1.0"}),
                                           timeout=900).read()
            break
        except Exception:
            if i == 3:
                raise
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        partes = []
        with z.open(z.namelist()[0]) as f:
            for ch in pd.read_csv(f, sep=";", dtype=str, chunksize=500_000, encoding="utf-8-sig",
                                  usecols=["SG_UF", "DE_FAIXA_ETARIA", "COBERTURA_ASSIST_PLAN", "QT_BENEFICIARIO_ATIVO"]):
                ch = ch[ch["COBERTURA_ASSIST_PLAN"].eq("Médico-hospitalar")]
                ch["QT_BENEFICIARIO_ATIVO"] = pd.to_numeric(ch["QT_BENEFICIARIO_ATIVO"], errors="coerce")
                partes.append(ch.groupby("DE_FAIXA_ETARIA")["QT_BENEFICIARIO_ATIVO"].sum())
    s = pd.concat(partes).groupby(level=0).sum().rename("beneficiarios").reset_index()
    s["uf"], s["ano"] = uf, ano
    print(uf, ano, int(s.beneficiarios.sum()), flush=True)
    return s


os.makedirs("tavi_savr/dados_ref", exist_ok=True)
with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(lambda t: um(*t), [(uf, a) for a in range(2021, 2026) for uf in UFS]))
pd.concat(res).to_csv("tavi_savr/dados_ref/ans_beneficiarios_junho_uf_faixa.csv", index=False)
