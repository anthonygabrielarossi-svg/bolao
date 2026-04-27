"""Sincroniza os jogos da Copa do Mundo com a API BSD.

Uso:
    python scripts/atualizar_jogos_copa.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db
from services.jogos_service import atualizar_jogos_copa


def main() -> int:
    init_db()

    resumo = atualizar_jogos_copa()
    print("Resumo final da atualizacao:")
    print(f"Total de eventos: {resumo['total_eventos']}")
    print(f"Eventos baixados: {resumo['baixados']}")
    print(f"Jogos inseridos: {resumo['inseridos']}")
    print(f"Jogos atualizados: {resumo['atualizados']}")
    print(f"Jogos sem alteracao: {resumo['sem_alteracao']}")
    print(f"Jogos finalizados: {resumo['finalizados']}")
    print(f"Jogos com fase nao mapeada: {resumo['nao_mapeados']}")
    print(f"Placeholders: {resumo['placeholders']}")
    print(f"Reais: {resumo['reais']}")
    print(f"Ranking recalculado: {resumo['ranking_recalculado']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
