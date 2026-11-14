#!/usr/bin/env python3
"""SIH-SP (serviços profissionais por AIH) dos procedimentos valvares — espelho healthbr-data (sih/sp/, SHA-256).

Serve para (1) identificar o profissional (SP_PF_CBO, SP_PF_DOC → pseudonimizar na análise) de TAVI e SAVR e
(2) decompor as AIH de cirurgias múltiplas/sequenciais (0415010012/0415020034) com CID aórtico, cujo procedimento
valvar só aparece aqui. Um registro SP entra se:
  - SP_ATOPROF (ato profissional) ou SP_PROCREA (procedimento da AIH) está em PROCS de extrair_valvas_sih.py; ou
  - SP_PROCREA é 0415010012/0415020034 e SP_CIDPRI é I35/I06/Q230/Q231.
Reaproveita baixar/sha256/cobertura de sih_crvm.py; retomável (parciais SP<UF><AA><MM>.csv).

Uso: python tavi_savr/extrair_valvas_sp.py --ini 2008 --cmpt-fim 202608 --saida saida_tavi/sp --workers 6
"""
import argparse
import json
import os
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sih_crvm as base  # noqa: E402

ESPELHO_SP = "https://data.sidneybissoli.com/sih/sp"
PROCS = ["0406030162", "0406011524", "0406010692", "0406010820", "0406011206", "0406010846", "0406010838",
         "0406010803", "0406010811", "0406010552", "0406011478", "0406030111", "0406010021", "0406011265"]
MULTIPLAS = ["0415010012", "0415020034"]
CID_PREFIXOS = ("I35", "I06", "Q230", "Q231")
lock = threading.Lock()


def filtro(t):
    ato = pc.utf8_trim_whitespace(t["SP_ATOPROF"])
    proc = pc.utf8_trim_whitespace(t["SP_PROCREA"])
    cid = pc.utf8_trim_whitespace(t["SP_CIDPRI"])
    vs = pa.array(PROCS)
    m = pc.or_(pc.is_in(ato, value_set=vs), pc.is_in(proc, value_set=vs))
    aort = pc.starts_with(cid, CID_PREFIXOS[0])
    for p in CID_PREFIXOS[1:]:
        aort = pc.or_(aort, pc.starts_with(cid, p))
    m = pc.or_(m, pc.and_(pc.is_in(proc, value_set=pa.array(MULTIPLAS)), aort))
    return t.filter(pc.fill_null(m, False))


def processar(tarefa, pasta, tmpdir, manifesto):
    uf, ano, mes = tarefa
    nome = f"SP{uf}{ano % 100:02d}{mes:02d}"
    chave = f"{ano}-{mes:02d}-{uf}"
    reg = {"arquivo": nome, "uf": uf, "ano": ano, "mes": mes}
    try:
        info = manifesto.get(chave)
        if info is None:
            raise FileNotFoundError(f"partição {chave} ausente no espelho")
        partes, total = [], 0
        for of in info["output_files"]:
            destino = os.path.join(tmpdir, chave + "_" + os.path.basename(of["path"]))
            base.baixar(f"{ESPELHO_SP}/{of['path'][len('sih/sp/'):]}", destino)
            try:
                if base.sha256(destino) != of["sha256"]:
                    raise ValueError(f"SHA-256 divergente em {of['path']}")
                f = pq.ParquetFile(destino)
                for i in range(f.metadata.num_row_groups):
                    t = f.read_row_group(i)
                    total += t.num_rows
                    t = filtro(t)
                    if t.num_rows:
                        partes.append(t)
            finally:
                os.remove(destino)
        df = pa.concat_tables(partes, promote_options="default").to_pandas() if partes else None
        csv = os.path.join(pasta, nome + ".csv")
        if df is None:
            open(csv + ".tmp", "w").close()
        else:
            df["arquivo_origem"] = nome
            df.to_csv(csv + ".tmp", index=False)
        os.replace(csv + ".tmp", csv)
        reg.update(status="lido", registros_arquivo=total, selecionados=0 if df is None else len(df),
                   origem=info.get("source_url", ""))
    except Exception as e:
        reg.update(status="falhou", erro=f"{type(e).__name__}: {e}")
    with lock:
        with open(os.path.join(pasta, "_cobertura.jsonl"), "a") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return reg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ini", type=int, default=2008)
    ap.add_argument("--cmpt-fim", type=int, default=202608)
    ap.add_argument("--saida", default="saida_tavi/sp")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    pasta = os.path.join(a.saida, "parciais")
    os.makedirs(pasta, exist_ok=True)
    mpath = os.path.join(a.saida, "manifest_sih_sp.json")
    if not os.path.exists(mpath):
        base.baixar(f"{ESPELHO_SP}/manifest.json", mpath)
    manifesto = json.load(open(mpath))["partitions"]
    meses = [(y, m) for y in range(a.ini, a.cmpt_fim // 100 + 1) for m in range(1, 13) if y * 100 + m <= a.cmpt_fim]
    # mais recentes primeiro: TAVI (2023+) fica pronta antes
    tarefas = [(uf, y, m) for y, m in sorted(meses, reverse=True) for uf in base.UFS]
    feitos = {f[:-4] for f in os.listdir(pasta) if f.endswith(".csv")}
    pend = [t for t in tarefas if f"SP{t[0]}{t[1] % 100:02d}{t[2]:02d}" not in feitos]
    print(f"{len(tarefas)} arquivos; {len(tarefas) - len(pend)} feitos; {len(pend)} pendentes", flush=True)
    tmpdir = tempfile.mkdtemp(prefix="sp_dl_", dir=a.saida)
    ok = falhas = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(processar, t, pasta, tmpdir, manifesto) for t in pend]
        for i, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            if r["status"] == "lido":
                ok += 1
            else:
                falhas += 1
                print(f"  FALHOU {r['arquivo']}: {r['erro']}", flush=True)
            if i % 100 == 0 or i == len(futs):
                print(f"  {i}/{len(futs)} (ok={ok}, falhas={falhas})", flush=True)
    os.rmdir(tmpdir)


if __name__ == "__main__":
    main()
