#!/usr/bin/env python3
"""Resumo das notas técnicas e-NatJus (CNJ) de TAVI com CID I35/I06 (extraídas por natjus_tavi.py).
Idade <18 anos tratada como erro de leitura (ausente). As marcas 'plano_operadora' e 'sus_mencionado' aparecem em 100%
das notas (texto-padrão do formulário) e não são usadas. Uma nota técnica = um pedido de parecer por um juiz (não uma
ação; o e-NatJus não cobre todos os tribunais). Saída: tavi_savr/resultados_judicializacao/."""
import os
import numpy as np
import pandas as pd
S = "tavi_savr/resultados_judicializacao"
os.makedirs(S, exist_ok=True)
d = pd.read_csv("tavi_savr/dados_ref/natjus_I35_procedimentos.csv")
d.loc[d.idade < 18, "idade"] = np.nan
t = d[d.tavi].copy()
t["periodo"] = np.where(t.ano <= 2023, "2020-2023 (pre-incorporation)", "2024-2026 (post-incorporation)")
t["faixa"] = pd.cut(t.idade, [17, 69, 74, 79, 200], labels=["<70", "70-74", "75-79", ">=80"])
ano = t.groupby("ano").agg(notas=("id", "size"), idade_mediana=("idade", "median"),
                           pct_menos75=("idade", lambda s: round(100 * (s.dropna() < 75).mean(), 1)),
                           pct_justica_federal=("esfera", lambda s: round(100 * s.eq("federal").sum() / s.notna().sum(), 1)))
ano.loc["total"] = [len(t), t.idade.median(), round(100 * (t.idade.dropna() < 75).mean(), 1),
                    round(100 * t.esfera.eq("federal").sum() / t.esfera.notna().sum(), 1)]
ano.to_csv(f"{S}/J1_notas_tavi_ano.csv")
per = pd.crosstab(t.periodo, t.faixa, normalize="index").mul(100).round(1)
per["n"] = t.groupby("periodo").size()
per["idade_mediana"] = t.groupby("periodo").idade.median()
per.to_csv(f"{S}/J2_idade_periodo.csv")
uf = t.uf_paciente.value_counts().rename("notas").to_frame()
uf["pct"] = (100 * uf.notas / uf.notas.sum()).round(1)
uf.to_csv(f"{S}/J3_uf_paciente.csv")
geral = pd.DataFrame([{"notas_I35_I06": 1251, "notas_procedimento": len(d), "notas_tavi": len(t),
                       "pct_tavi": round(100 * len(t) / len(d), 1), "pct_masculino": round(100 * t.sexo.eq("masculino").mean(), 1),
                       "idade_ausente": int(t.idade.isna().sum())}])
geral.to_csv(f"{S}/J0_geral.csv", index=False)
print(geral.T, ano, per, uf.head(10), sep="\n\n")
