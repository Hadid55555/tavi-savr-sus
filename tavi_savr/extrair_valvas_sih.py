#!/usr/bin/env python3
"""TAVI × SAVR no SIH/SUS: extração das AIH (RD) de procedimentos valvares e das internações com CID valvar aórtico.

Reaproveita sih_crvm.py (espelho healthbr-data, SHA-256 por arquivo, parciais retomáveis); só troca o filtro e as
colunas. Um registro entra se:
  - PROC_REA está em PROCS (TAVI, SAVR e afins, valvoplastias); ou
  - PROC_REA é um código novo nas faixas 0406011520–0406011999 ou 0406030160–0406030299 (captura vias de TAVI ou
    códigos criados depois de 2019 que ainda não conhecemos); ou
  - DIAG_PRINC começa com I35, I06 ou Q230/Q231 (doença valvar aórtica, qualquer procedimento ou tratamento clínico).

Uso: python tavi_savr/extrair_valvas_sih.py --ini 2008 --fim 2025 --cmpt-fim 202608 --saida saida_tavi --workers 8
"""
import os
import sys

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sih_crvm as base  # noqa: E402

PROCS = {
    "0406030162": "TAVI", "0406011524": "TAVI",
    "0406010692": "SAVR", "0406010820": "Valvar múltipla", "0406011206": "Valvar + CRVM",
    "0406010846": "Tubo valvado", "0406010838": "Raiz da aorta", "0406010803": "Plástica valvar",
    "0406010811": "Plástica valvar + CRVM", "0406010552": "Ross", "0406011478": "Ross",
    "0406030111": "Valvoplastia aórtica percutânea", "0406010021": "Abertura estenose aórtica",
    "0406011265": "Abertura estenose aórtica",
}
CID_PREFIXOS = ("I35", "I06", "Q230", "Q231")

base.PROCS = PROCS
base.COLUNAS = base.COLUNAS + [f"DIAGSEC{i}" for i in range(1, 10)] + ["RACA_COR", "GESTAO", "COMPLEX", "FINANC"]


def filtro(t):
    proc = pc.utf8_trim_whitespace(t["PROC_REA"])
    diag = pc.utf8_trim_whitespace(t["DIAG_PRINC"])
    m = pc.is_in(proc, value_set=pa.array(list(PROCS)))
    for ini, fim in (("0406011520", "0406011999"), ("0406030160", "0406030299")):
        m = pc.or_(m, pc.and_(pc.greater_equal(proc, ini), pc.less_equal(proc, fim)))
    for p in CID_PREFIXOS:
        m = pc.or_(m, pc.starts_with(diag, p))
    return t.filter(pc.fill_null(m, False))


def ler_espelho(chave, info, tmpdir):
    tabelas, total = [], 0
    for of in info["output_files"]:
        destino = os.path.join(tmpdir, chave + "_" + os.path.basename(of["path"]))
        base.baixar(f"{base.ESPELHO}/{of['path'][len('sih/rd/'):]}", destino)
        try:
            if base.sha256(destino) != of["sha256"]:
                raise ValueError(f"SHA-256 divergente em {of['path']}")
            arq = pq.ParquetFile(destino)
            presentes = [c for c in base.COLUNAS if c in arq.schema_arrow.names]
            t = arq.read(columns=presentes)
            total += t.num_rows
            tabelas.append(filtro(t).to_pandas(ignore_metadata=True))
        finally:
            os.remove(destino)
    df = pd.concat(tabelas, ignore_index=True) if tabelas else pd.DataFrame()
    return df, total


base.ler_espelho = ler_espelho

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", type=int, default=2008)
    ap.add_argument("--fim", type=int, default=2025)
    ap.add_argument("--cmpt-fim", type=int, default=None)
    ap.add_argument("--saida", default="saida_tavi")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    a.fonte = "espelho"
    tarefas = base.extrair(a)
    cob = base.cobertura(a, tarefas)
    print(cob["status"].value_counts().to_string())
