#!/usr/bin/env python3
"""Auditoria de completude do TISS hospitalar (ANS): internações por plano (ID_PLANO) e ano, 2015–2025.

Relê só os arquivos CONS (um registro por internação) e grava, por UF/mês, a contagem de internações por ID_PLANO e
modalidade da operadora. Serve para definir planos "continuamente observados" (com internações em todos os anos de um
período) e refazer a série de TAVI/SAVR restrita a eles (sensibilidade à entrada de novas operadoras no envio do TISS).
Reaproveita baixar/ler_zip de extrair_tiss_ans.py. Retomável.

Uso: python -I tavi_savr/tiss_completude_planos.py --saida saida_tavi/tiss_planos --workers 8
"""
import argparse
import importlib.util
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

spec = importlib.util.spec_from_file_location("tiss", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                     "extrair_tiss_ans.py"))
tiss = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tiss)
lock = threading.Lock()


def processar(uf, ano, mes, pasta):
    chave = f"{uf}_{ano}{mes:02d}"
    reg = {"arquivo": chave, "uf": uf, "ano": ano, "mes": mes}
    try:
        b = tiss.baixar(f"{tiss.BASE}/{ano}/{uf}/{chave}_HOSP_CONS.zip")
        cons = tiss.ler_zip(b, usecols=["ID_PLANO", "CD_MODALIDADE"])
        g = cons.groupby(["ID_PLANO", "CD_MODALIDADE"]).size().rename("internacoes").reset_index()
        g["uf"], g["ano"], g["mes"] = uf, ano, mes
        g.to_csv(os.path.join(pasta, chave + ".csv.tmp"), index=False)
        os.replace(os.path.join(pasta, chave + ".csv.tmp"), os.path.join(pasta, chave + ".csv"))
        reg.update(status="lido", internacoes=len(cons), planos=int(g["ID_PLANO"].nunique()))
    except Exception as e:
        reg.update(status="falhou", erro=f"{type(e).__name__}: {e}")
    with lock:
        with open(os.path.join(pasta, "_cobertura.jsonl"), "a") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return reg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", type=int, default=2015)
    ap.add_argument("--fim", type=int, default=2025)
    ap.add_argument("--saida", default="saida_tavi/tiss_planos")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    pasta = os.path.join(a.saida, "parciais")
    os.makedirs(pasta, exist_ok=True)
    tarefas = [(uf, y, m) for y in range(a.ini, a.fim + 1) for m in range(1, 13) for uf in tiss.UFS]
    feitos = {f[:-4] for f in os.listdir(pasta) if f.endswith(".csv")}
    pend = [t for t in tarefas if f"{t[0]}_{t[1]}{t[2]:02d}" not in feitos]
    print(f"{len(tarefas)} UF/mês; {len(pend)} pendentes", flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(processar, *t, pasta) for t in pend]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            if r["status"] != "lido":
                print(f"  FALHOU {r['arquivo']}: {r.get('erro')}", flush=True)
            if i % 200 == 0 or i == len(futs):
                print(f"  {i}/{len(futs)}", flush=True)


if __name__ == "__main__":
    main()
