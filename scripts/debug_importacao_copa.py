"""Mostra uma amostra dos jogos importados da Copa do Mundo.

Uso:
    python scripts/debug_importacao_copa.py
"""

from __future__ import annotations

from collections import Counter
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import FASE_NAO_MAPEADA, init_db, listar_jogos
from services.jogos_service import listar_jogos_importados_debug


def main() -> int:
    init_db()

    jogos = listar_jogos()
    if not jogos:
        print("Nenhum jogo importado ainda.")
        return 0

    contagem_fases = Counter(jogo.fase or FASE_NAO_MAPEADA for jogo in jogos)
    total = len(jogos)
    total_grupos = contagem_fases.get("Fase de Grupos", 0)
    total_sem_fase = contagem_fases.get(FASE_NAO_MAPEADA, 0)
    total_mata_mata = total - total_grupos - total_sem_fase
    total_placeholders = sum(1 for jogo in jogos if getattr(jogo, "is_placeholder_bracket", False))

    print(f"Total na base: {total}")
    print(f"Fase de Grupos: {total_grupos}")
    print(f"Mata-mata: {max(total_mata_mata, 0)}")
    print(f"Sem fase mapeada: {total_sem_fase}")
    print(f"Placeholders: {total_placeholders}")
    print(f"Reais: {total - total_placeholders}")
    print()
    print("Primeiros 20 jogos importados:")

    amostra = listar_jogos_importados_debug(20)
    for indice, item in enumerate(amostra, start=1):
        print(
            f"{indice:02d}. api_id={item['api_id']} | "
            f"{item['time_casa']} x {item['time_fora']} | "
            f"data={item['data_jogo'] or '-'} | "
            f"round={item['round_number'] if item['round_number'] is not None else '-'} | "
            f"fase={item['fase']} | grupo={item['grupo'] or '-'} | status={item['status']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
