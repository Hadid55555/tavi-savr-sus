#!/usr/bin/env python3
"""TAVI × SAVR na saúde suplementar: extração do TISS hospitalar (dados abertos da ANS), 2015–2025.

Fonte: https://dadosabertos.ans.gov.br/FTP/PDA/TISS/HOSPITALAR/<ano>/<UF>/<UF>_<AAAAMM>_HOSP_{CONS,DET}.zip
  CONS: um registro por evento de atenção (internação): faixa etária, sexo, municípios, permanência, UTI, caráter,
        motivo de saída, CID_1–4, modalidade da operadora.
  DET:  itens do evento (procedimentos TUSS, diárias, materiais), ligados pelo ID_EVENTO_ATENCAO_SAUDE.
A ANS não publica hash por arquivo: guardamos tamanho (Content-Length) e nº de linhas lidas.

Um evento entra se tiver no DET um código de PROCS ou da faixa 30912290–30912399 (procedimentos transcateter novos),
ou se o CID_1 do CONS for I35/I06/Q230/Q231. Para cada UF/mês grava em <saida>/parciais/:
  <UF>_<AAAAMM>.csv           eventos selecionados (colunas do CONS + códigos TUSS de interesse do evento)
  _cobertura.jsonl            status, linhas lidas em CONS/DET, IDs duplicados, eventos por faixa etária (para
                              avaliar a completude do envio ano a ano)
Retomável: o que já tem parcial é pulado.

Uso: python -I tavi_savr/extrair_tiss_ans.py --ini 2015 --fim 2025 --saida saida_tavi/tiss --workers 6
"""
import argparse
import io
import json
import os
import threading
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

BASE = "https://dadosabertos.ans.gov.br/FTP/PDA/TISS/HOSPITALAR"
UFS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC "
       "SE SP TO").split()
PROCS = {
    "30912296": "TAVI",
    "30902053": "Troca valvar",
    "30902045": "Plastia valvar",
    "30902029": "Cirurgia multivalvar",
    "30902037": "Comissurotomia valvar",
    "30902010": "Ampliação do anel valvar",
    "30903033": "CRVM + cirurgia valvar",
    "30903025": "CRVM",
    "30912245": "Valvoplastia percutânea arterial/venosa",
    "30912253": "Valvoplastia percutânea transeptal",
}
CID_PREFIXOS = ("I35", "I06", "Q230", "Q231")
lock = threading.Lock()


def baixar(url, tentativas=5):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sih-crvm/1.0"})
            with urllib.request.urlopen(req, timeout=600) as r:
                tam = int(r.headers.get("Content-Length") or 0)
                dados = r.read()
            if tam and len(dados) != tam:
                raise IOError(f"tamanho {len(dados)} != {tam}")
            return dados
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if i == tentativas - 1:
                raise
        except Exception:
            if i == tentativas - 1:
                raise
        time.sleep(2 ** (i + 1))


def ler_zip(dados, usecols=None):
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nome = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(nome) as f:
            return pd.read_csv(f, sep=";", dtype=str, keep_default_na=False, usecols=usecols,
                               encoding="utf-8-sig", encoding_errors="replace")


def processar(uf, ano, mes, pasta):
    chave = f"{uf}_{ano}{mes:02d}"
    reg = {"arquivo": chave, "uf": uf, "ano": ano, "mes": mes}
    try:
        det_b = baixar(f"{BASE}/{ano}/{uf}/{chave}_HOSP_DET.zip")
        det = ler_zip(det_b, usecols=["ID_EVENTO_ATENCAO_SAUDE", "CD_PROCEDIMENTO"])
        reg["det_bytes"], reg["det_linhas"] = len(det_b), len(det)
        del det_b
        p = det["CD_PROCEDIMENTO"].str.strip().str.strip('"')
        m = p.isin(PROCS) | p.between("30912290", "30912399")
        alvo = det.loc[m, ["ID_EVENTO_ATENCAO_SAUDE"]].assign(cod=p[m])
        del det
        cods = alvo.drop_duplicates().groupby("ID_EVENTO_ATENCAO_SAUDE")["cod"].agg(lambda s: "|".join(sorted(s)))

        cons_b = baixar(f"{BASE}/{ano}/{uf}/{chave}_HOSP_CONS.zip")
        cons = ler_zip(cons_b)
        reg["cons_bytes"], reg["cons_linhas"] = len(cons_b), len(cons)
        reg["cons_ids_duplicados"] = int(cons["ID_EVENTO_ATENCAO_SAUDE"].duplicated().sum())
        reg["eventos_por_faixa"] = cons["FAIXA_ETARIA"].str.strip().value_counts().to_dict()
        cid = cons["CID_1"].str.strip().str.upper()
        reg["cid1_preenchido"] = int(cid.ne("").sum())
        sel = cons[cons["ID_EVENTO_ATENCAO_SAUDE"].isin(cods.index) | cid.str.startswith(CID_PREFIXOS)].copy()
        sel["cods_tuss"] = sel["ID_EVENTO_ATENCAO_SAUDE"].map(cods).fillna("")
        reg["eventos_dets_sem_cons"] = int((~cods.index.isin(cons["ID_EVENTO_ATENCAO_SAUDE"])).sum())
        sel["arquivo_origem"] = chave
        sel.to_csv(os.path.join(pasta, chave + ".csv.tmp"), index=False)
        os.replace(os.path.join(pasta, chave + ".csv.tmp"), os.path.join(pasta, chave + ".csv"))
        reg.update(status="lido", selecionados=len(sel),
                   por_codigo={c: int(cods.str.contains(c).sum()) for c in PROCS})
    except urllib.error.HTTPError as e:
        reg.update(status="ausente" if e.code == 404 else "falhou", erro=f"HTTP {e.code}")
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
    ap.add_argument("--saida", default="saida_tavi/tiss")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    pasta = os.path.join(a.saida, "parciais")
    os.makedirs(pasta, exist_ok=True)
    tarefas = [(uf, ano, mes) for ano in range(a.ini, a.fim + 1) for mes in range(1, 13) for uf in UFS]
    feitos = {f[:-4] for f in os.listdir(pasta) if f.endswith(".csv")}
    pend = [t for t in tarefas if f"{t[0]}_{t[1]}{t[2]:02d}" not in feitos]
    print(f"{len(tarefas)} UF/mês; {len(tarefas) - len(pend)} feitos; {len(pend)} pendentes", flush=True)
    ok = falhas = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(processar, *t, pasta) for t in pend]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            if r["status"] == "lido":
                ok += 1
            else:
                falhas += 1
                print(f"  {r['status'].upper()} {r['arquivo']}: {r.get('erro')}", flush=True)
            if i % 100 == 0 or i == len(futs):
                print(f"  {i}/{len(futs)} (ok={ok}, outros={falhas})", flush=True)


if __name__ == "__main__":
    main()
