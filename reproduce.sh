#!/usr/bin/env bash
# Runs every analysis of the package, in order, from the repository root.
set -euo pipefail
cd "$(dirname "$0")"
for s in contagens_fase1 taxas_75mais nacional_sus_ans auditorias tiss_completude_analise geografia analises_v2 \
         sensibilidade_razao carga_capacidade sim_mortalidade_padronizada modelo_uf natjus_analise; do
  echo "== tavi_savr/$s.py"
  python3 "tavi_savr/$s.py" > /dev/null
done
echo "== tavi_savr/manuscrito/tabela1.py";      python3 tavi_savr/manuscrito/tabela1.py > /dev/null
echo "== tavi_savr/manuscrito/figuras_tavi.py"; python3 tavi_savr/manuscrito/figuras_tavi.py > /dev/null
echo "== tavi_savr/manuscrito/graphical_abstract.py"; python3 tavi_savr/manuscrito/graphical_abstract.py > /dev/null
echo "done"
