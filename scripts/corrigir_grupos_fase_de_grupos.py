"""Corrige os grupos dos jogos da fase de grupos da Copa do Mundo.

Uso:
    python scripts/corrigir_grupos_fase_de_grupos.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import init_db
from services.jogos_service import corrigir_grupos_fase_de_grupos


def main() -> int:
    init_db()

    resumo = corrigir_grupos_fase_de_grupos()
    print("Resumo final da correção de grupos:")
    print(f"Total de jogos verificados: {resumo['total']}")
    print(f"Jogos atualizados: {resumo['atualizados']}")
    print(f"Jogos sem grupo mapeado: {resumo['nao_mapeados']}")
    for grupo, quantidade in sorted(resumo["por_grupo"].items()):
        print(f"{grupo}: {quantidade} jogos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
