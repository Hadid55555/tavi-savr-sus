#!/usr/bin/env python3
"""Judicialização: notas técnicas do e-NatJus (CNJ) com CID de estenose/doença valvar aórtica (I35.0, I35.2, I35.8,
I35.9, I06.0, I06.2), 2020–2026. As notas são pedidas por juízes em ações de saúde. Lê a lista pública
(api/pesquisaPublica/listar) já salva e baixa o PDF de cada nota de "Procedimento", extraindo SÓ variáveis agregáveis
(sem nomes): ano, NAT responsável, idade, sexo, UF do município do paciente, esfera (federal/estadual), se a tecnologia é
TAVI (texto com "transcateter", "TAVI", "TAVR", "implante percutâneo"), se há plano de saúde/operadora como parte.
Uso: python -I tavi_savr/natjus_tavi.py <notas_I35.json> <pasta_pdf> <saida.csv>
"""
import json
import os
import re
import sys
import time
import urllib.request

import pandas as pd
from pypdf import PdfReader

notas = [x for x in json.load(open(sys.argv[1])) if x["tecnologia"] == "Procedimento"]
pasta = sys.argv[2]
os.makedirs(pasta, exist_ok=True)
linhas = []
for x in notas:
    pdf = os.path.join(pasta, f"{x['idNotaTecnica']}.pdf")
    if not os.path.exists(pdf):
        u = f"https://www.pje.jus.br/e-natjus/notaTecnica-dados.php?output=pdf&token={x['token']}"
        for k in range(3):
            try:
                b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
                open(pdf, "wb").write(b)
                break
            except Exception:
                time.sleep(3)
        time.sleep(0.4)
    r = {"id": x["idNotaTecnica"], "ano": x["horaCriado"][-4:], "nat": x["natResponsavel"], "cid": x["cid"][:5]}
    try:
        t = " ".join((p.extract_text() or "") for p in PdfReader(pdf).pages[:4])
        tl = t.lower()
        m = re.search(r"idade:\s*(\d+)", tl)
        r["idade"] = int(m.group(1)) if m else None
        m = re.search(r"sexo:\s*(masculino|feminino)", tl)
        r["sexo"] = m.group(1) if m else None
        m = re.search(r"cidade:\s*[^/\n]+/([a-z]{2})", tl)
        r["uf_paciente"] = m.group(1).upper() if m else None
        m = re.search(r"esfera/órgão:\s*justiça\s*(federal|estadual)", tl)
        r["esfera"] = m.group(1) if m else None
        r["tavi"] = bool(re.search(r"transcateter|\btavi\b|\btavr\b|implante percut", tl))
        r["plano_operadora"] = bool(re.search(r"plano de saúde|operadora|saúde suplementar", tl))
        r["sus_mencionado"] = bool(re.search(r"\bsus\b|sistema único", tl))
    except Exception as e:
        r["erro"] = str(e)[:80]
    linhas.append(r)
pd.DataFrame(linhas).to_csv(sys.argv[3], index=False)
print(len(linhas))
