"""Corrige as fases dos jogos da Copa do Mundo 2026 ja importados.

Uso:
    python scripts/corrigir_fases_copa.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db
from services.jogos_service import corrigir_fases_copa


def main() -> int:
    init_db()

    resumo = corrigir_fases_copa()
    print("Resumo final da correcao de fases:")
    print(f"Total de jogos: {resumo['total']}")
    print(f"Jogos atualizados: {resumo['atualizados']}")
    print(f"Jogos nao mapeados: {resumo['nao_mapeados']}")
    print("Distribuicao por fase:")
    for fase, quantidade in sorted(resumo["por_fase"].items()):
        print(f"  - {fase}: {quantidade}")
    print("Confirmacoes:")
    for round_number, fase in sorted(resumo["confirmacoes"].items()):
        print(f"  - round_number {round_number}: {fase}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
