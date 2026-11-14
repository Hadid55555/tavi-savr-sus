#!/usr/bin/env python3
"""Extração de microdados SIH/SUS (AIH reduzida, RD) de revascularização miocárdica (CRVM).

Procedimentos (SIGTAP):
  Com CEC: 0406010927, 0406010935
  Sem CEC: 0406010943, 0406010951

Fontes suportadas (--fonte):
  espelho  Espelho público healthbr-data (https://data.sidneybissoli.com/sih/rd/), Parquet
           convertido 1:1 dos RD<UF><AA><MM>.dbc oficiais do DATASUS. Cada partição traz
           SHA-256, que é conferido no download. Padrão, porque o FTP do DATASUS costuma
           recusar conexões de IPs fora do Brasil.
  ftp      FTP oficial ftp://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados/
           (requer `pip install datasus-dbc dbfread`).

Os arquivos são organizados por competência (ANO_CMPT/MES_CMPT). A janela de download vai
de jan/<ini> até jan/<fim+1>; o recorte final é pelo ano da internação (DT_INTER) ou da saída.

Retomável: cada arquivo UF/mês gera um CSV parcial em <saida>/parciais/ e uma linha em
<saida>/parciais/_cobertura.jsonl; o que já está feito é pulado.

Uso:
  python sih_crvm.py --ini 2008 --fim 2025 --ano-ref internacao --saida saida_crvm
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd

ESPELHO = "https://data.sidneybissoli.com/sih/rd"
FTP = "ftp://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados"

UFS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC "
       "SE SP TO").split()

PROCS = {
    "0406010927": "Com CEC", "0406010935": "Com CEC",
    "0406010943": "Sem CEC", "0406010951": "Sem CEC",
}
PROC_NOME = {
    "0406010927": "Revascularização miocárdica c/ uso de extracorpórea",
    "0406010935": "Revascularização miocárdica c/ uso de extracorpórea (c/ 2 ou mais enxertos)",
    "0406010943": "Revascularização miocárdica s/ uso de extracorpórea",
    "0406010951": "Revascularização miocárdica s/ uso de extracorpórea (c/ 2 ou mais enxertos)",
}

VALORES = ["VAL_SH", "VAL_SP", "VAL_SADT", "VAL_RN", "VAL_ACOMP", "VAL_ORTP", "VAL_SANGUE",
           "VAL_SADTSR", "VAL_TRANSP", "VAL_OBSANG", "VAL_PED1AC", "VAL_UTI", "VAL_TOT", "US_TOT",
           "VAL_SH_FED", "VAL_SP_FED", "VAL_SH_GES", "VAL_SP_GES"]
UTI = ["UTI_MES_IN", "UTI_MES_AN", "UTI_MES_AL", "UTI_MES_TO", "UTI_INT_TO", "MARCA_UTI"]
COLUNAS = (["ANO_CMPT", "MES_CMPT", "UF_ZI", "ESPEC", "N_AIH", "IDENT", "PROC_REA", "MORTE",
            "DIAS_PERM", "IDADE", "COD_IDADE", "SEXO", "DT_INTER", "DT_SAIDA", "DIAG_PRINC",
            "DIAG_SECUN", "CID_MORTE", "CAR_INT", "CNES", "MUNIC_MOV", "MUNIC_RES", "COBRANCA",
            "NAT_JUR"] + VALORES + UTI)
INTEIROS = ["MORTE", "DIAS_PERM", "IDADE", "UTI_MES_IN", "UTI_MES_AN", "UTI_MES_AL",
            "UTI_MES_TO", "UTI_INT_TO"]

UF_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
           "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
           "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
           "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
REGIAO = {"1": "Norte", "2": "Nordeste", "3": "Sudeste", "4": "Sul", "5": "Centro-Oeste"}

DICIONARIO = {
    "ANO_CMPT": "Ano de processamento (competência) da AIH",
    "MES_CMPT": "Mês de processamento (competência) da AIH",
    "UF_ZI": "Código do município gestor",
    "ESPEC": "Especialidade do leito",
    "N_AIH": "Número da AIH",
    "IDENT": "Identificação da AIH (1 = principal, 3 = continuação, 5 = longa permanência)",
    "PROC_REA": "Procedimento realizado (SIGTAP)",
    "MORTE": "Óbito na internação (1 = sim, 0 = não)",
    "DIAS_PERM": "Dias de permanência",
    "IDADE": "Idade, na unidade de COD_IDADE",
    "COD_IDADE": "Unidade da idade (2 = dias, 3 = meses, 4 = anos, 5 = 100 anos + IDADE)",
    "SEXO": "Sexo (1 = masculino, 2 ou 3 = feminino, 0/9 = ignorado)",
    "DT_INTER": "Data de internação (AAAAMMDD)",
    "DT_SAIDA": "Data de saída (AAAAMMDD)",
    "DIAG_PRINC": "CID-10 do diagnóstico principal",
    "DIAG_SECUN": "CID-10 do diagnóstico secundário (pouco preenchido após 2015)",
    "CID_MORTE": "CID-10 da causa do óbito",
    "CAR_INT": "Caráter da internação (01 = eletivo, 02 = urgência, 03-06 = acidentes/lesões)",
    "CNES": "Código CNES do estabelecimento",
    "MUNIC_MOV": "Município do estabelecimento (IBGE, 6 dígitos)",
    "MUNIC_RES": "Município de residência do paciente (IBGE, 6 dígitos)",
    "COBRANCA": "Motivo de saída/permanência",
    "NAT_JUR": "Natureza jurídica do estabelecimento (a partir de 2012; antes ver NATUREZA)",
    "VAL_SH": "Valor de serviços hospitalares (R$)",
    "VAL_SP": "Valor de serviços profissionais (R$)",
    "VAL_SADT": "Valor de SADT (R$)",
    "VAL_RN": "Valor de recém-nascido (R$)",
    "VAL_ACOMP": "Valor de acompanhante (R$)",
    "VAL_ORTP": "Valor de órtese e prótese (R$)",
    "VAL_SANGUE": "Valor de sangue (R$)",
    "VAL_SADTSR": "Valor de SADT sem remuneração (R$)",
    "VAL_TRANSP": "Valor de transporte (R$)",
    "VAL_OBSANG": "Valor de órtese e prótese de sangue (R$)",
    "VAL_PED1AC": "Valor de pediatria 1ª consulta (R$)",
    "VAL_UTI": "Valor de UTI (R$) — ver aba qualidade: contido em VAL_SH?",
    "VAL_TOT": "Valor total da AIH (R$) = componentes (exceto VAL_UTI) + complementos federal e do gestor",
    "VAL_SH_FED": "Complemento federal de serviços hospitalares (R$); preenchido a partir de 2023 em parte das AIH",
    "VAL_SP_FED": "Complemento federal de serviços profissionais (R$)",
    "VAL_SH_GES": "Complemento do gestor (estadual/municipal) de serviços hospitalares (R$)",
    "VAL_SP_GES": "Complemento do gestor (estadual/municipal) de serviços profissionais (R$)",
    "US_TOT": "Valor total em dólar (US$)",
    "UTI_MES_IN": "Dias de UTI no mês — UTI inicial",
    "UTI_MES_AN": "Dias de UTI no mês — mês anterior",
    "UTI_MES_AL": "Dias de UTI no mês — mês da alta",
    "UTI_MES_TO": "Total de dias de UTI na internação (usado como 'dias de UTI')",
    "UTI_INT_TO": "Total de dias em unidade intermediária",
    "MARCA_UTI": "Tipo de UTI utilizada",
    "grupo": "Derivada: Com CEC (0406010927, 0406010935) / Sem CEC (0406010943, 0406010951)",
    "procedimento": "Derivada: nome do procedimento SIGTAP",
    "uf": "Derivada: UF do atendimento (2 primeiros dígitos de MUNIC_MOV)",
    "regiao": "Derivada: região do atendimento (1º dígito de MUNIC_MOV)",
    "uf_res": "Derivada: UF de residência (2 primeiros dígitos de MUNIC_RES)",
    "ano_internacao": "Derivada: ano de DT_INTER",
    "ano_saida": "Derivada: ano de DT_SAIDA",
    "ano_cmpt": "Derivada: ANO_CMPT numérico",
    "idade_anos": "Derivada: idade em anos (COD_IDADE 2/3 -> 0; 4 -> IDADE; 5 -> 100 + IDADE)",
    "faixa_etaria": "Derivada: faixa etária em anos",
    "sexo_desc": "Derivada: Masculino / Feminino / Ignorado",
    "n_aih_duplicado": "Derivada: N_AIH aparece mais de uma vez no recorte (1 = sim)",
    "arquivo_origem": "Derivada: arquivo RD<UF><AA><MM> de onde veio o registro",
}

lock = threading.Lock()


def baixar(url, destino, tentativas=4):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sih-crvm/1.0 (+https://github.com/hadid55555/sih-crvm)"})
            with urllib.request.urlopen(req, timeout=300) as r, open(destino, "wb") as f:
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
            return
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(2 ** (i + 1))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_espelho(chave, info, tmpdir):
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    tabelas, total = [], 0
    for of in info["output_files"]:
        destino = os.path.join(tmpdir, chave + "_" + os.path.basename(of["path"]))
        baixar(f"{ESPELHO}/{of['path'][len('sih/rd/'):]}", destino)
        try:
            if sha256(destino) != of["sha256"]:
                raise ValueError(f"SHA-256 divergente em {of['path']}")
            arq = pq.ParquetFile(destino)
            presentes = [c for c in COLUNAS if c in arq.schema_arrow.names]
            t = arq.read(columns=presentes)
            total += t.num_rows
            t = t.filter(pc.is_in(t["PROC_REA"], value_set=__import__("pyarrow").array(list(PROCS))))
            tabelas.append(t.to_pandas(ignore_metadata=True))
        finally:
            os.remove(destino)
    df = pd.concat(tabelas, ignore_index=True) if tabelas else pd.DataFrame()
    return df, total


def ler_ftp(uf, ano, mes, tmpdir):
    import datasus_dbc
    from dbfread import DBF

    nome = f"RD{uf}{ano % 100:02d}{mes:02d}"
    dbc = os.path.join(tmpdir, nome + ".dbc")
    dbf = os.path.join(tmpdir, nome + ".dbf")
    baixar(f"{FTP}/{nome}.dbc", dbc)
    try:
        datasus_dbc.decompress(dbc, dbf)
        tab = DBF(dbf, encoding="latin-1", raw=False, char_decode_errors="replace")
        regs = [{k: (str(v) if v is not None else "") for k, v in r.items()} for r in tab]
        df = pd.DataFrame(regs)
        total = len(df)
        df = df[df["PROC_REA"].isin(PROCS)][[c for c in COLUNAS if c in df.columns]]
    finally:
        for p in (dbc, dbf):
            if os.path.exists(p):
                os.remove(p)
    return df.reset_index(drop=True), total


def processar(tarefa, args, pasta, tmpdir, manifesto):
    uf, ano, mes = tarefa
    nome = f"RD{uf}{ano % 100:02d}{mes:02d}"
    parcial = os.path.join(pasta, nome + ".csv")
    try:
        if args.fonte == "espelho":
            chave = f"{ano}-{mes:02d}-{uf}"
            info = manifesto.get(chave)
            if info is None:
                raise FileNotFoundError(f"partição {chave} ausente no espelho")
            df, total = ler_espelho(chave, info, tmpdir)
            origem = info.get("source_url", "")
        else:
            df, total = ler_ftp(uf, ano, mes, tmpdir)
            origem = f"{FTP}/{nome}.dbc"
        for c in COLUNAS:
            if c not in df.columns:
                df[c] = pd.NA
        df = df[COLUNAS]
        df["arquivo_origem"] = nome
        df.to_csv(parcial + ".tmp", index=False)
        os.replace(parcial + ".tmp", parcial)
        reg = {"arquivo": nome, "uf": uf, "ano": ano, "mes": mes, "status": "lido",
               "registros_arquivo": int(total), "registros_crvm": int(len(df)),
               "fonte": args.fonte, "origem": origem}
    except Exception as e:
        reg = {"arquivo": nome, "uf": uf, "ano": ano, "mes": mes, "status": "falhou",
               "registros_arquivo": None, "registros_crvm": None, "fonte": args.fonte,
               "origem": "", "erro": f"{type(e).__name__}: {e}"}
    with lock:
        with open(os.path.join(pasta, "_cobertura.jsonl"), "a") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return reg


def janela(args):
    """Competências de jan/<ini> até <cmpt_fim> (AAAAMM; padrão: jan/<fim+1>)."""
    fim = args.cmpt_fim or (args.fim + 1) * 100 + 1
    meses = [(a, m) for a in range(args.ini, fim // 100 + 1) for m in range(1, 13) if a * 100 + m <= fim]
    return [(uf, a, m) for a, m in meses for uf in UFS]


def extrair(args):
    pasta = os.path.join(args.saida, "parciais")
    os.makedirs(pasta, exist_ok=True)
    tarefas = janela(args)

    manifesto = {}
    if args.fonte == "espelho":
        mpath = os.path.join(args.saida, "manifest_sih_rd.json")
        if not os.path.exists(mpath):
            baixar(f"{ESPELHO}/manifest.json", mpath)
        manifesto = json.load(open(mpath))["partitions"]

    feitos = {f[:-4] for f in os.listdir(pasta) if f.startswith("RD") and f.endswith(".csv")}
    pendentes = [t for t in tarefas if f"RD{t[0]}{t[1] % 100:02d}{t[2]:02d}" not in feitos]
    print(f"{len(tarefas)} arquivos na janela; {len(tarefas) - len(pendentes)} já feitos; "
          f"{len(pendentes)} pendentes", flush=True)

    tmpdir = tempfile.mkdtemp(prefix="sih_dl_", dir=args.saida)
    ok = falhas = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(processar, t, args, pasta, tmpdir, manifesto) for t in pendentes]
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
    return tarefas


def cobertura(args, tarefas):
    pasta = os.path.join(args.saida, "parciais")
    regs = {}
    path = os.path.join(pasta, "_cobertura.jsonl")
    if os.path.exists(path):
        for linha in open(path):
            r = json.loads(linha)
            regs[r["arquivo"]] = r  # a última tentativa vale
    linhas = []
    for uf, a, m in tarefas:
        nome = f"RD{uf}{a % 100:02d}{m:02d}"
        r = regs.get(nome, {"arquivo": nome, "uf": uf, "ano": a, "mes": m, "status": "não tentado"})
        if os.path.exists(os.path.join(pasta, nome + ".csv")):
            r["status"] = "lido"
        linhas.append(r)
    return pd.DataFrame(linhas)


def consolidar(args):
    pasta = os.path.join(args.saida, "parciais")
    arquivos = sorted(f for f in os.listdir(pasta) if f.startswith("RD") and f.endswith(".csv"))
    partes = [pd.read_csv(os.path.join(pasta, f), dtype=str, keep_default_na=False) for f in arquivos]
    df = pd.concat([p for p in partes if len(p)], ignore_index=True)
    for c in VALORES:
        df[c] = pd.to_numeric(df[c].str.strip(), errors="coerce")
    for c in INTEIROS:
        df[c] = pd.to_numeric(df[c].str.strip(), errors="coerce").astype("Int64")
    df["grupo"] = df["PROC_REA"].map(PROCS)
    df["procedimento"] = df["PROC_REA"].map(PROC_NOME)
    mov = df["MUNIC_MOV"].str.strip()
    df["uf"] = mov.str[:2].map(UF_IBGE)
    df["regiao"] = mov.str[:1].map(REGIAO)
    df["uf_res"] = df["MUNIC_RES"].str.strip().str[:2].map(UF_IBGE)
    dt_i = pd.to_datetime(df["DT_INTER"].str.strip(), format="%Y%m%d", errors="coerce")
    dt_s = pd.to_datetime(df["DT_SAIDA"].str.strip(), format="%Y%m%d", errors="coerce")
    df["ano_internacao"] = dt_i.dt.year.astype("Int64")
    df["ano_saida"] = dt_s.dt.year.astype("Int64")
    df["ano_cmpt"] = pd.to_numeric(df["ANO_CMPT"], errors="coerce").astype("Int64")
    cod = df["COD_IDADE"].str.strip()
    idade = df["IDADE"].astype("Float64")
    df["idade_anos"] = np.select(
        [cod.eq("4").to_numpy(), cod.eq("5").to_numpy(), cod.isin(["0", "1", "2", "3"]).to_numpy()],
        [idade.to_numpy(dtype=float, na_value=np.nan), 100 + idade.to_numpy(dtype=float, na_value=np.nan), 0.0],
        default=np.nan)
    df["faixa_etaria"] = pd.cut(df["idade_anos"], [-1, 39, 49, 59, 69, 79, 200],
                                labels=["<40", "40-49", "50-59", "60-69", "70-79", "80+"]).astype(str)
    df.loc[df["idade_anos"].isna(), "faixa_etaria"] = "Ignorado"
    df["sexo_desc"] = df["SEXO"].str.strip().map({"1": "Masculino", "2": "Feminino", "3": "Feminino"}).fillna("Ignorado")
    return df


def metricas(g):
    out = {
        "procedimentos": len(g),
        "obitos": int(g["MORTE"].fillna(0).sum()),
        "mortalidade_pct": round(100 * g["MORTE"].fillna(0).mean(), 2) if len(g) else np.nan,
        "dias_perm_media": round(g["DIAS_PERM"].astype(float).mean(), 2),
        "dias_perm_mediana": g["DIAS_PERM"].astype(float).median(),
        "dias_uti_media": round(g["UTI_MES_TO"].astype(float).mean(), 2),
        "dias_uti_mediana": g["UTI_MES_TO"].astype(float).median(),
        "pct_com_uti": round(100 * (g["UTI_MES_TO"].astype(float) > 0).mean(), 2) if len(g) else np.nan,
        "idade_media": round(g["idade_anos"].mean(), 1),
        "pct_masculino": round(100 * g["SEXO"].str.strip().eq("1").mean(), 2) if len(g) else np.nan,
        "custo_medio": round(g["VAL_TOT"].mean(), 2),
        "custo_total": round(g["VAL_TOT"].sum(), 2),
    }
    for c in VALORES:
        if c == "VAL_TOT":
            continue
        out[f"{c}_medio"] = round(g[c].mean(), 2)
        out[f"{c}_total"] = round(g[c].sum(), 2)
    return pd.Series(out)


def tabela(df, chaves):
    return df.groupby(chaves, dropna=False, observed=True).apply(metricas, include_groups=False).reset_index()


def qualidade(df):
    linhas = []

    def add(teste, n, base, obs=""):
        linhas.append({"teste": teste, "n": int(n), "base": int(base),
                       "pct": round(100 * n / base, 2) if base else np.nan, "observacao": obs})

    N = len(df)
    sh, uti, tot = df["VAL_SH"], df["VAL_UTI"], df["VAL_TOT"]
    com_uti = uti > 0
    add("VAL_UTI > 0", com_uti.sum(), N)
    add("VAL_UTI <= VAL_SH (entre AIHs com VAL_UTI > 0)", (com_uti & (uti <= sh + 0.01)).sum(), com_uti.sum(),
        "100% é compatível com VAL_UTI contido em VAL_SH")
    add("VAL_UTI > VAL_SH (entre AIHs com VAL_UTI > 0)", (com_uti & (uti > sh + 0.01)).sum(), com_uti.sum(),
        "qualquer caso aqui refuta VAL_UTI ⊂ VAL_SH")
    comp = ["VAL_SH", "VAL_SP", "VAL_SADT", "VAL_RN", "VAL_ACOMP", "VAL_ORTP", "VAL_SANGUE",
            "VAL_SADTSR", "VAL_TRANSP", "VAL_OBSANG", "VAL_PED1AC"]
    soma_sem_uti = df[comp].fillna(0).sum(axis=1)
    soma_com_uti = soma_sem_uti + uti.fillna(0)
    sh_sp = df[["VAL_SH", "VAL_SP"]].fillna(0).sum(axis=1)
    compl = df[["VAL_SH_FED", "VAL_SP_FED", "VAL_SH_GES", "VAL_SP_GES"]].fillna(0).sum(axis=1)
    add("VAL_TOT == soma componentes SEM VAL_UTI (±0,01)", ((tot - soma_sem_uti).abs() <= 0.01).sum(), N,
        "se ~100%, VAL_UTI não entra separado no total (já está em VAL_SH)")
    add("VAL_TOT == soma componentes COM VAL_UTI (±0,01)", ((tot - soma_com_uti).abs() <= 0.01).sum(), N,
        "se ~100% só quando VAL_UTI = 0, somar VAL_UTI duplica")
    add("  idem, só entre AIHs com VAL_UTI > 0: SEM VAL_UTI",
        (com_uti & ((tot - soma_sem_uti).abs() <= 0.01)).sum(), com_uti.sum())
    add("  idem, só entre AIHs com VAL_UTI > 0: COM VAL_UTI",
        (com_uti & ((tot - soma_com_uti).abs() <= 0.01)).sum(), com_uti.sum())
    add("VAL_TOT == soma componentes SEM VAL_UTI + complementos federal/gestor (±0,01)",
        ((tot - soma_sem_uti - compl).abs() <= 0.01).sum(), N, "fechamento completo do VAL_TOT")
    add("AIH com complemento federal (VAL_SH_FED + VAL_SP_FED > 0)",
        (df[["VAL_SH_FED", "VAL_SP_FED"]].fillna(0).sum(axis=1) > 0).sum(), N)
    add("AIH com complemento do gestor (VAL_SH_GES + VAL_SP_GES > 0)",
        (df[["VAL_SH_GES", "VAL_SP_GES"]].fillna(0).sum(axis=1) > 0).sum(), N)
    add("VAL_TOT == VAL_SH + VAL_SP (±0,01)", ((tot - sh_sp).abs() <= 0.01).sum(), N)
    add("UTI_MES_TO > 0 e VAL_UTI == 0", ((df["UTI_MES_TO"].fillna(0) > 0) & ~com_uti).sum(), N)
    add("UTI_MES_TO == 0 e VAL_UTI > 0", ((df["UTI_MES_TO"].fillna(0) == 0) & com_uti).sum(), N)
    add("N_AIH duplicado", df["n_aih_duplicado"].eq(1).sum(), N, "mesma AIH em mais de uma linha (reapresentação/continuação)")
    add("IDENT = 5 (longa permanência)", df["IDENT"].str.strip().eq("5").sum(), N)
    add("DT_INTER inválida/ausente", df["ano_internacao"].isna().sum(), N)
    add("DT_SAIDA inválida/ausente", df["ano_saida"].isna().sum(), N)
    add("DT_SAIDA < DT_INTER", (pd.to_datetime(df["DT_SAIDA"], format="%Y%m%d", errors="coerce")
                                < pd.to_datetime(df["DT_INTER"], format="%Y%m%d", errors="coerce")).sum(), N)
    add("MUNIC_MOV sem UF válida", df["uf"].isna().sum(), N)
    add("Idade ignorada", df["idade_anos"].isna().sum(), N)
    add("Idade < 18 anos", (df["idade_anos"] < 18).sum(), N)
    add("Sexo ignorado", df["sexo_desc"].eq("Ignorado").sum(), N)
    add("MORTE = 1 sem CID_MORTE", (df["MORTE"].eq(1) & df["CID_MORTE"].str.strip().isin(["", "0000"])).sum(),
        df["MORTE"].eq(1).sum())
    add("NAT_JUR vazio", df["NAT_JUR"].str.strip().eq("").sum(), N, "campo só existe a partir de ~2012")
    add("VAL_TOT <= 0", (tot <= 0).sum(), N)
    return pd.DataFrame(linhas)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ini", type=int, default=2008)
    ap.add_argument("--fim", type=int, default=2025)
    ap.add_argument("--ano-ref", choices=["internacao", "saida"], default="internacao")
    ap.add_argument("--saida", default="saida_crvm")
    ap.add_argument("--fonte", choices=["espelho", "ftp"], default="espelho")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cmpt-fim", type=int, default=None,
                    help="última competência AAAAMM a baixar (padrão: jan do ano seguinte a --fim); "
                         "use uma competência mais recente para captar AIHs processadas com atraso")
    ap.add_argument("--so-consolidar", action="store_true", help="não baixa; só consolida os parciais")
    args = ap.parse_args()
    args.workers = max(4, min(8, args.workers))
    os.makedirs(args.saida, exist_ok=True)

    if args.so_consolidar:
        tarefas = janela(args)
    else:
        tarefas = extrair(args)

    cob = cobertura(args, tarefas)
    lidos = cob["status"].eq("lido")
    print(f"\nArquivos na janela: {len(cob)} | lidos: {lidos.sum()} | faltando: {(~lidos).sum()}")
    if (~lidos).any():
        print("Faltando:", ", ".join(cob.loc[~lidos, "arquivo"]))

    todos = consolidar(args)
    rotulo = f"{args.ini}_{args.fim}"
    ref_col = {"internacao": "ano_internacao", "saida": "ano_saida"}
    no_periodo = {k: todos[todos[c].between(args.ini, args.fim)].copy() for k, c in ref_col.items()}
    for k, d in no_periodo.items():
        d["n_aih_duplicado"] = d["N_AIH"].duplicated(keep=False).astype(int)
        d.sort_values([ref_col[k], "uf", "N_AIH"]).to_csv(
            os.path.join(args.saida, f"crvm_{rotulo}_{k}_microdados.csv"), index=False, encoding="utf-8-sig")
    df = no_periodo[args.ano_ref]
    ano = ref_col[args.ano_ref]

    abas = {}
    abas["validacao_ano_grupo"] = tabela(df, [ano, "grupo"])
    abas["por_procedimento"] = tabela(df, [ano, "PROC_REA", "procedimento", "grupo"])
    cobx = cob.copy()
    abas["cobertura_arquivos"] = cobx
    abas["regiao_ano"] = tabela(df, [ano, "regiao", "grupo"])
    abas["uf_ano"] = tabela(df, [ano, "uf", "regiao", "grupo"])
    abas["sexo_ano"] = tabela(df, [ano, "sexo_desc", "grupo"])
    abas["faixa_etaria_ano"] = tabela(df, [ano, "faixa_etaria", "grupo"])
    abas["cnes_ano"] = tabela(df, [ano, "CNES", "uf", "MUNIC_MOV"])
    act = df.groupby("CNES").agg(uf=("uf", lambda s: s.mode().iat[0] if s.notna().any() else None),
                                 municipio=("MUNIC_MOV", lambda s: s.mode().iat[0]),
                                 primeiro_ano=(ano, "min"), ultimo_ano=(ano, "max"),
                                 anos_ativos=(ano, "nunique"))
    abas["cnes_total"] = act.join(df.groupby("CNES").apply(metricas, include_groups=False)).reset_index() \
        .sort_values("procedimentos", ascending=False)

    comp = []
    for nome, col, base in [("internacao", "ano_internacao", no_periodo["internacao"]),
                            ("saida", "ano_saida", no_periodo["saida"]),
                            ("processamento", "ano_cmpt", todos[todos["ano_cmpt"].between(args.ini, args.fim)])]:
        t = base.groupby([col, "grupo"]).size().rename(f"n_{nome}")
        t.index.names = ["ano", "grupo"]
        comp.append(t)
    cmp_df = pd.concat(comp, axis=1).fillna(0).astype(int).reset_index()
    cmp_df["dif_saida_vs_internacao"] = cmp_df["n_saida"] - cmp_df["n_internacao"]
    cmp_df["dif_processamento_vs_internacao"] = cmp_df["n_processamento"] - cmp_df["n_internacao"]
    abas["comparacao_anos"] = cmp_df
    abas["qualidade"] = qualidade(df)
    fonte = ("Espelho healthbr-data (https://data.sidneybissoli.com/sih/rd/), Parquet 1:1 dos DBC "
             "oficiais do DATASUS; SHA-256 conferido por arquivo") if args.fonte == "espelho" else f"FTP DATASUS {FTP}"
    dic = pd.DataFrame([{"variavel": k, "descricao": v} for k, v in DICIONARIO.items()])
    dic = pd.concat([dic, pd.DataFrame([
        {"variavel": "(fonte)", "descricao": fonte},
        {"variavel": "(recorte)", "descricao": f"Competências jan/{args.ini}–{str(args.cmpt_fim or (args.fim + 1) * 100 + 1)}; ano de referência = {ano} "
                                               f"entre {args.ini} e {args.fim}"},
        {"variavel": "(métricas)", "descricao": "procedimentos = nº de AIHs; mortalidade_pct = 100·média(MORTE); "
                                                "dias_uti = UTI_MES_TO; custo = VAL_TOT; componentes = VAL_* médio e total. "
                                                "Valores em R$ nominais (sem correção monetária)."},
    ])], ignore_index=True)
    abas["dicionario"] = dic

    xlsx = os.path.join(args.saida, f"crvm_{rotulo}_{args.ano_ref}_tabelas.xlsx")
    with pd.ExcelWriter(xlsx, engine="xlsxwriter") as w:
        for nome, t in abas.items():
            t.to_excel(w, sheet_name=nome, index=False)
            w.sheets[nome].freeze_panes(1, 0)
            w.sheets[nome].autofilter(0, 0, len(t), max(len(t.columns) - 1, 0))

    # Verificação independente: relê o CSV final e confere com as tabelas.
    chk = pd.read_csv(os.path.join(args.saida, f"crvm_{rotulo}_{args.ano_ref}_microdados.csv"),
                      dtype={"PROC_REA": str, "N_AIH": str}, low_memory=False)
    v = abas["validacao_ano_grupo"]
    erros = []
    if len(chk) != v["procedimentos"].sum():
        erros.append(f"n CSV {len(chk)} != soma tabela {v['procedimentos'].sum()}")
    if abs(chk["VAL_TOT"].sum() - v["custo_total"].sum()) > 1:
        erros.append(f"VAL_TOT CSV {chk['VAL_TOT'].sum():.2f} != tabela {v['custo_total'].sum():.2f}")
    if chk["MORTE"].sum() != v["obitos"].sum():
        erros.append("óbitos divergem")
    for nome in ["regiao_ano", "uf_ano", "sexo_ano", "faixa_etaria_ano", "cnes_ano", "por_procedimento", "cnes_total"]:
        if abas[nome]["procedimentos"].sum() != len(chk):
            erros.append(f"{nome}: soma {abas[nome]['procedimentos'].sum()} != {len(chk)}")
    print("\nRegistros por ano e grupo (", ano, "):")
    print(chk.pivot_table(index=ano, columns="grupo", values="N_AIH", aggfunc="count", margins=True,
                          margins_name="Total").fillna(0).astype(int).to_string())
    print(f"\nTotal: {len(chk)} AIHs | óbitos {int(chk['MORTE'].sum())} | VAL_TOT R$ {chk['VAL_TOT'].sum():,.2f}")
    print("Verificação independente:", "OK" if not erros else "FALHOU -> " + "; ".join(erros))
    print("Saídas:", xlsx, "e CSVs em", args.saida)
    return 0 if not erros else 1


if __name__ == "__main__":
    sys.exit(main())
